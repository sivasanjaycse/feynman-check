"""
demo/feynman/batch.py - Cohort Aggregator & Professor Escalation Pipeline.

Implements Member 4 responsibilities for Socratic Feynman Check & Batch Gap Ping:
1. Persistence of student sessions to data/students/{student_id}.json
2. Scanning and deterministic aggregation of fallacy clusters across the cohort
3. Dynamic concept support:
   - Tier 1: Dynamic LLM synthesis via demo/feynman/prompts/remediation.md
   - Tier 2: Dynamic parsing of data/concepts/{concept_id}.md for known fallacies
   - Tier 3: Deterministic offline fallback (FALLACY_KNOWLEDGE_BASE)
4. Telemetry tracking in data/batch_telemetry.json
5. Threshold evaluation (BATCH_ALERT_THRESHOLD = 3)
6. 2-Minute Remediation Brief generation in reports/INSTRUCTOR_ALERT_<date>.md
7. Human-in-the-Loop review gates:
   - Interactive CLI ([A]cknowledge / [D]ismiss)
   - Slice Store / Web callback integration via slice.callback.ask & web/expert.py
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from .schema import (
    BatchMisconceptionCluster,
    ProfessorEscalationReport,
    StudentSessionRecord,
)
from .stub import CANNED_CLUSTER, CANNED_ESCALATION_REPORT

# ---------------------------------------------------------------------------
# Architecture Constants
# ---------------------------------------------------------------------------
BATCH_ALERT_THRESHOLD: int = 3
DEFAULT_STUDENTS_DIR: Path = Path("data/students")
DEFAULT_CONCEPTS_DIR: Path = Path("data/concepts")
DEFAULT_TELEMETRY_PATH: Path = Path("data/batch_telemetry.json")
DEFAULT_REPORTS_DIR: Path = Path("reports")
DEFAULT_PROMPTS_DIR: Path = Path("demo/feynman/prompts")


# ---------------------------------------------------------------------------
# Mock Email Sender — Replace with real SMTP for production
# ---------------------------------------------------------------------------

def send_email(
    subject: str,
    body: str,
    recipient: str = "professor@university.edu",
) -> None:
    """Mock email sender — prints to terminal. Replace with real SMTP for production."""
    print("\n" + "=" * 70)
    print(f"\033[1;33m📧 EMAIL SENT TO: {recipient}\033[0m")
    print(f"\033[1m📋 SUBJECT: {subject}\033[0m")
    print("-" * 70)
    print(body)
    print("=" * 70 + "\n")

# Curated offline fallback knowledge base for instant demo execution
FALLACY_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    "TLB_MISS_EQUALS_DISK_IO": {
        "title": "Conflating TLB Miss with Page Fault / Disk Swap",
        "derailment": (
            "Students assume that a Translation Lookaside Buffer (TLB) cache miss means "
            "the data is absent from physical RAM and immediately triggers a secondary storage read. "
            "They overlook that the MMU checks the in-memory Page Table in RAM first."
        ),
        "remediation_suggestion": (
            "Draw the 3-Tier Hierarchy on chalkboard:\n"
            "  (1) TLB Cache -> (2) RAM Page Table -> (3) Disk Swap.\n"
            "Key Takeaway: A TLB miss is resolved in RAM 99% of the time via page table walking "
            "without disk involvement. Disk read only occurs if Page Table valid bit is 0."
        ),
    },
    "OFFSET_MODIFIED_DURING_TRANSLATION": {
        "title": "Asserting Offset Modification during Address Translation",
        "derailment": (
            "Students assume that virtual offset bits are transformed or recalculated during "
            "virtual address translation. In reality, page size equals frame size, so offset bits pass "
            "directly into the physical address unchanged."
        ),
        "remediation_suggestion": (
            "Draw side-by-side Page vs Frame diagram showing 4KB boundaries.\n"
            "Key Takeaway: Address translation only maps Virtual Page Number (VPN) to Physical Frame "
            "Number (PFN); offset bits pass through unmodified."
        ),
    },
    "CIRCULAR_WAIT_ALONE_IS_DEADLOCK": {
        "title": "Circular Wait Alone Treated as Deadlock",
        "derailment": (
            "Students assume any cycle in a resource allocation graph implies deadlock, forgetting "
            "that in multi-instance resource systems, an un-blocked process can release an instance "
            "and break the cycle."
        ),
        "remediation_suggestion": (
            "Draw a 2-instance resource graph with a cycle where a 3rd process holds and releases.\n"
            "Key Takeaway: All 4 Coffman conditions must hold simultaneously; in multi-instance systems, "
            "a cycle is a necessary but NOT sufficient condition for deadlock."
        ),
    },
    "STARVATION_EQUALS_DEADLOCK": {
        "title": "Conflating Starvation with Deadlock",
        "derailment": (
            "Students conflate temporary indefinite delay caused by unfair scheduling priority "
            "with an unresolvable circular dependency."
        ),
        "remediation_suggestion": (
            "Draw Priority Queue vs Circular Dependency graph.\n"
            "Key Takeaway: Starvation resolves when high-priority load subsides; Deadlock can never "
            "resolve without external preemption or termination."
        ),
    },
    "ADVERSARIAL_INJECTION_OR_EVASION": {
        "title": "Prompt Injection or Evasion Attempt",
        "derailment": (
            "Submission attempted to bypass conceptual verification using prompt injection meta-prompts."
        ),
        "remediation_suggestion": (
            "Enforce strict conceptual guardrails and remind students that invariant checks are mandatory."
        ),
    },
}


# ---------------------------------------------------------------------------
# Dynamic Concept Extraction: Parse Markdown Ground Truth
# ---------------------------------------------------------------------------

def load_concept_fallacies_from_markdown(
    concept_id: str,
    concepts_dir: Path | str = DEFAULT_CONCEPTS_DIR,
) -> Dict[str, Dict[str, str]]:
    """
    Dynamically extracts known fallacy patterns and pedagogical counters
    from data/concepts/{concept_id}.md.
    Enables adding any new concept (e.g., cpu_scheduling.md, concurrency.md)
    without modifying Python source code.
    """
    cdir = Path(concepts_dir)
    md_file = cdir / f"{concept_id}.md"
    if not md_file.exists():
        candidates = list(cdir.glob(f"*{concept_id}*.md"))
        if candidates:
            md_file = candidates[0]
        else:
            return {}

    try:
        content = md_file.read_text(encoding="utf-8")
    except Exception:
        return {}

    fallacies: Dict[str, Dict[str, str]] = {}
    tag_pattern = re.compile(r"^###\s+`([A-Z0-9_]+)`", re.MULTILINE)
    matches = list(tag_pattern.finditer(content))
    if not matches:
        # Fallback for files without backticks
        tag_pattern = re.compile(r"^###\s+([A-Z0-9_]{3,})", re.MULTILINE)
        matches = list(tag_pattern.finditer(content))

    for i, match in enumerate(matches):
        tag = match.group(1).strip()
        if tag == "I" or tag.startswith("INVARIANT"):
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end]

        desc_m = re.search(r"-\s+\*\*Description:\*\*\s*(.+?)(?=\n-|\n\n|$)", block, re.DOTALL)
        desc = desc_m.group(1).strip().replace("\n", " ") if desc_m else ""

        example_m = re.search(r"-\s+\*\*Example flawed claim:\*\*\s*(.+?)(?=\n-|\n\n|$)", block, re.DOTALL)
        example_claim = example_m.group(1).strip().replace("\n", " ") if example_m else ""

        counter_m = re.search(r"-\s+\*\*Pedagogical counter:\*\*\s*(.+?)(?=\n-|\n\n|$)", block, re.DOTALL)
        counter = counter_m.group(1).strip().replace("\n", " ") if counter_m else ""

        title = tag.replace("_", " ").title()
        derailment = desc or f"Misconception regarding {title}."
        if counter:
            remediation = (
                f"Pedagogical Intervention:\n"
                f"  {counter}\n"
                f"Key Takeaway: {counter}"
            )
        else:
            remediation = f"Review invariants for {concept_id.replace('_', ' ').title()} regarding {title}."

        fallacies[tag] = {
            "title": title,
            "derailment": derailment,
            "example_claim": example_claim,
            "pedagogical_counter": counter,
            "remediation_suggestion": remediation,
        }

    return fallacies


def get_concept_fallacy_info(
    fallacy_tag: str,
    concept_id: str = "oop_lecture_1",
    concepts_dir: Path | str = DEFAULT_CONCEPTS_DIR,
) -> Dict[str, str]:
    """
    Retrieves fallacy pedagogical information dynamically with three-tier fallback:
    1. Static Knowledge Base (if rich ASCII diagrams exist, e.g. 3-tier hierarchy)
    2. Dynamic extraction from data/concepts/{concept_id}.md
    3. Generic heuristic fallback based on the tag name
    """
    if fallacy_tag in FALLACY_KNOWLEDGE_BASE:
        return FALLACY_KNOWLEDGE_BASE[fallacy_tag]

    md_fallacies = load_concept_fallacies_from_markdown(concept_id, concepts_dir)
    if fallacy_tag in md_fallacies:
        return md_fallacies[fallacy_tag]

    title = fallacy_tag.replace("_", " ").title()
    return {
        "title": title,
        "derailment": f"Student mental models diverge on {title} mechanics.",
        "remediation_suggestion": (
            f"Review the foundational lecture invariants for {concept_id.replace('_', ' ').title()} "
            f"concerning {title}."
        ),
    }


# ---------------------------------------------------------------------------
# 1. Student Session Persistence
# ---------------------------------------------------------------------------

def save_student_session(
    record: StudentSessionRecord | Dict[str, Any],
    student_dir: Path | str = DEFAULT_STUDENTS_DIR,
) -> Path:
    """
    Persists a single student session audit record to data/students/{student_id}.json.
    Accepts a StudentSessionRecord instance or a compatible dictionary.
    """
    if isinstance(record, dict):
        validated_record = StudentSessionRecord.model_validate(record)
    else:
        validated_record = record

    target_dir = Path(student_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / f"{validated_record.student_id}.json"
    file_path.write_text(validated_record.model_dump_json(indent=2), encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# 2. Scanning Student Records
# ---------------------------------------------------------------------------

def scan_student_records(
    student_dir: Path | str = DEFAULT_STUDENTS_DIR,
) -> List[StudentSessionRecord]:
    """
    Scans and deserializes all JSON student records in data/students/*.json.
    Returns a list of valid StudentSessionRecord instances.
    """
    target_dir = Path(student_dir)
    if not target_dir.exists():
        return []

    records: List[StudentSessionRecord] = []
    for json_file in sorted(target_dir.glob("*.json")):
        try:
            content = json_file.read_text(encoding="utf-8")
            record = StudentSessionRecord.model_validate_json(content)
            records.append(record)
        except Exception:
            continue

    return records


# ---------------------------------------------------------------------------
# 3. Telemetry Aggregation & Clustering
# ---------------------------------------------------------------------------

def aggregate_cohort_telemetry(
    records: Optional[List[StudentSessionRecord]] = None,
    student_dir: Path | str = DEFAULT_STUDENTS_DIR,
    output_file: Optional[Path | str] = DEFAULT_TELEMETRY_PATH,
    concepts_dir: Path | str = DEFAULT_CONCEPTS_DIR,
) -> Dict[str, BatchMisconceptionCluster]:
    """
    Deterministically aggregates fallacy clusters across student records.
    Groups records by `tagged_fallacy` and tallies occurrence count and quotes.
    Writes telemetry snapshot to data/batch_telemetry.json.
    """
    if records is None:
        records = scan_student_records(student_dir)

    groups: Dict[str, List[StudentSessionRecord]] = {}
    for rec in records:
        tag = rec.tagged_fallacy
        if tag and tag.strip():
            groups.setdefault(tag.strip(), []).append(rec)

    clusters: Dict[str, BatchMisconceptionCluster] = {}
    for tag, group_records in groups.items():
        concept_id = group_records[0].concept_id if group_records else "oop_lecture_1"

        # Collect distinct quotes from initial text and revisions
        quotes: List[str] = []
        for r in group_records:
            if r.initial_text and r.initial_text.strip():
                snip = r.initial_text.strip()
                if len(snip) > 120:
                    snip = snip[:117] + "..."
                if snip not in quotes:
                    quotes.append(snip)
            for rev in r.student_revisions:
                if rev and rev.strip():
                    rev_snip = rev.strip()
                    if len(rev_snip) > 120:
                        rev_snip = rev_snip[:117] + "..."
                    if rev_snip not in quotes:
                        quotes.append(rev_snip)

        if not quotes:
            quotes = [f"Student exhibited misconception tagged as {tag}"]

        # Retrieve dynamic pedagogical info (from markdown ground truth or static fallback)
        kb_entry = get_concept_fallacy_info(tag, concept_id, concepts_dir=concepts_dir)
        suggestion = kb_entry.get(
            "remediation_suggestion",
            f"Review lecture invariants for {concept_id.replace('_', ' ').title()} regarding {tag}.",
        )

        cluster = BatchMisconceptionCluster(
            fallacy_tag=tag,
            occurrence_count=len(group_records),
            affected_student_ids=[r.student_id for r in group_records],
            sample_student_quotes=quotes[:5],
            remediation_suggestion=suggestion,
        )
        clusters[tag] = cluster

    if output_file is not None:
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_students_scanned": len(records),
            "cluster_count": len(clusters),
            "clusters": {k: v.model_dump() for k, v in clusters.items()},
        }
        out_path.write_text(json.dumps(telemetry_payload, indent=2), encoding="utf-8")

    return clusters


# ---------------------------------------------------------------------------
# 4. Threshold Evaluation
# ---------------------------------------------------------------------------

def check_escalation_threshold(
    clusters: Dict[str, BatchMisconceptionCluster],
    threshold: int = BATCH_ALERT_THRESHOLD,
) -> List[BatchMisconceptionCluster]:
    """
    Evaluates clusters against the alert threshold (default >= 3).
    Returns list of clusters that breached the threshold.
    """
    breached: List[BatchMisconceptionCluster] = []
    for cluster in clusters.values():
        if cluster.occurrence_count >= threshold:
            breached.append(cluster)
    return breached


# ---------------------------------------------------------------------------
# 5. Remediation Brief & Report Generator
# ---------------------------------------------------------------------------

def generate_instructor_alert(
    cluster: BatchMisconceptionCluster,
    concept_id: str = "oop_lecture_1",
    reports_dir: Path | str = DEFAULT_REPORTS_DIR,
    concepts_dir: Path | str = DEFAULT_CONCEPTS_DIR,
    prompts_dir: Path | str = DEFAULT_PROMPTS_DIR,
    date_str: Optional[str] = None,
    call_llm: Optional[Callable] = None,
    stub_mode: bool = True,
) -> Tuple[ProfessorEscalationReport, Path]:
    """
    Generates the 2-Minute Remediation Brief formatted for the course professor.
    Supports dynamic LLM synthesis when call_llm is provided; otherwise uses
    concept markdown invariants or static fallback.
    Writes markdown report to reports/INSTRUCTOR_ALERT_<date>.md.
    Returns (ProfessorEscalationReport, Path).
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    target_dir = Path(reports_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    report_id = f"INSTRUCTOR_ALERT_{date_str}_{concept_id.upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    # Tier 1: Dynamic LLM Remediation synthesis if call_llm is provided
    if call_llm is not None:
        try:
            prompt_file = Path(prompts_dir) / "remediation.md"
            system_prompt = (
                prompt_file.read_text(encoding="utf-8")
                if prompt_file.exists()
                else "You are an expert pedagogical advisor for the course instructor."
            )

            concept_file = Path(concepts_dir) / f"{concept_id}.md"
            concept_text = (
                concept_file.read_text(encoding="utf-8")
                if concept_file.exists()
                else f"Concept: {concept_id}"
            )

            user_prompt = (
                f"Course Concept: {concept_id}\n\n"
                f"Ground Truth Invariants:\n{concept_text}\n\n"
                f"Fallacy Tag: {cluster.fallacy_tag}\n"
                f"Occurrence Count: {cluster.occurrence_count}\n"
                f"Student Quotes:\n" + "\n".join(f"- {q}" for q in cluster.sample_student_quotes)
            )

            llm_result = call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                schema=BatchMisconceptionCluster,
                step="remediation",
            )
            if hasattr(llm_result, "remediation_suggestion") and llm_result.remediation_suggestion:
                cluster.remediation_suggestion = llm_result.remediation_suggestion
        except Exception:
            pass

    # Tier 2 & 3: Dynamic or offline fallback pedagogical info
    kb_entry = get_concept_fallacy_info(cluster.fallacy_tag, concept_id, concepts_dir=concepts_dir)
    fallacy_title = kb_entry.get("title", cluster.fallacy_tag.replace("_", " ").title())
    derailment = kb_entry.get(
        "derailment",
        "Students' mental models derailed from physical architecture realities.",
    )
    remediation_text = cluster.remediation_suggestion

    # Format quotes section
    quote_lines = []
    for i, q in enumerate(cluster.sample_student_quotes, start=1):
        stud_id = (
            cluster.affected_student_ids[i - 1]
            if i - 1 < len(cluster.affected_student_ids)
            else "Anonymous"
        )
        quote_lines.append(f'  - "{q}" *(Student {stud_id})*')
    quotes_formatted = "\n".join(quote_lines)

    # Build Markdown Content
    report_md = f"""# [URGENT CONCEPT GAP DETECTED: CS8492 - {concept_id.replace('_', ' ').title()}]

**Date:** {date_str}  
**Report ID:** `{report_id}`  
**Status:** `WAITING_FOR_PROFESSOR`  
**Threshold Trigger:** {cluster.occurrence_count} students (Threshold $\\ge$ {BATCH_ALERT_THRESHOLD})

---

## 1. Summary of Misconception
- **Fallacy Name:** **{fallacy_title}** (`{cluster.fallacy_tag}`)
- **Affected Students:** {cluster.occurrence_count} students: {', '.join(cluster.affected_student_ids)}
- **Pedagogical Root Cause:**
  {derailment}

## 2. Anonymized Evidence
Direct excerpts demonstrating the misconception:
{quotes_formatted}

## 3. Recommended 2-Minute Lecture Intervention
{remediation_text}

---

> ### Human-in-the-Loop Review Gate
> **Action Required from Course Instructor:**
> - `[A]` **Acknowledge:** Add 2-minute remediation slide to next lecture queue.
> - `[D]` **Dismiss:** Mark as pedagogical noise.
"""

    report_file = target_dir / f"INSTRUCTOR_ALERT_{date_str}.md"
    report_file.write_text(report_md, encoding="utf-8")

    generic_file = target_dir / "INSTRUCTOR_ALERT.md"
    generic_file.write_text(report_md, encoding="utf-8")

    report_model = ProfessorEscalationReport(
        report_id=report_id,
        concept_id=concept_id,
        timestamp=timestamp,
        cluster=cluster,
        status="WAITING_ACK",
    )

    return report_model, report_file


# ---------------------------------------------------------------------------
# 6. Human-in-the-Loop Review Gate
# ---------------------------------------------------------------------------

def escalate_to_professor(
    report: ProfessorEscalationReport,
    mode: Literal["cli", "web", "auto_ack"] = "cli",
    action: Optional[str] = None,
    store: Any = None,
    run_id: Optional[str] = None,
    settings: Any = None,
) -> ProfessorEscalationReport:
    """
    Executes the Human-in-the-Loop review gate.
    - 'cli': Prompts professor in terminal for [A]cknowledge / [D]ismiss.
    - 'auto_ack': Automatically marks as ACKNOWLEDGED (used in automated batch tests).
    - 'web': Suspends run on a human by parking a Question in slice.store.Store.
    """
    if mode == "web" and store is not None and run_id is not None:
        try:
            from slice import callback
            question_text = (
                f"{report.cluster.occurrence_count} students exhibited identical fallacy: "
                f"[{report.cluster.fallacy_tag}]. Acknowledge 2-minute remediation slide? [A/D]"
            )
            context = {
                "report_id": report.report_id,
                "concept_id": report.concept_id,
                "fallacy_tag": report.cluster.fallacy_tag,
                "sample_quotes": "\n".join(report.cluster.sample_student_quotes),
                "remediation": report.cluster.remediation_suggestion,
                "resume_state": "complete",
            }
            callback.ask(store, run_id, question_text, context, settings)
            return report
        except Exception:
            pass

    if mode == "auto_ack":
        report.status = "ACKNOWLEDGED"
        return report

    if action is not None:
        act = action.strip().upper()
        if act.startswith("A"):
            report.status = "ACKNOWLEDGED"
        elif act.startswith("D"):
            report.status = "DISMISSED"
        return report

    print("\n" + "=" * 76)
    print(f" [!] PROFESSOR GAP ALERT: {report.concept_id.upper()} ({report.report_id})")
    print(f" Fallacy: {report.cluster.fallacy_tag} ({report.cluster.occurrence_count} students)")
    print("-" * 76)
    for q in report.cluster.sample_student_quotes[:3]:
        print(f"   * Quote: \"{q}\"")
    print("-" * 76)
    print(" 2-Minute Remediation Proposal:")
    for line in report.cluster.remediation_suggestion.splitlines():
        print(f"   {line}")
    print("=" * 76)

    try:
        user_input = input("Acknowledge to queue remediation in next lecture? [A]cknowledge / [D]ismiss: ").strip().upper()
        if user_input.startswith("A"):
            report.status = "ACKNOWLEDGED"
            print(" [OK] Alert ACKNOWLEDGED. Remediation slide queued for next lecture.\n")
        else:
            report.status = "DISMISSED"
            print(" [-] Alert DISMISSED by professor.\n")
    except (EOFError, KeyboardInterrupt):
        report.status = "WAITING_ACK"

    return report


# ---------------------------------------------------------------------------
# 7. Hook for demo/feynman/flow.py Integration
# ---------------------------------------------------------------------------

def check_and_escalate_batch(
    ctx: Any = None,
    student_dir: Path | str = DEFAULT_STUDENTS_DIR,
    threshold: int = BATCH_ALERT_THRESHOLD,
    interactive: bool = False,
    call_llm: Optional[Callable] = None,
) -> Optional[ProfessorEscalationReport]:
    """
    Hook called automatically by demo/feynman/flow.py:log_student_session_state.
    Scans student records, aggregates telemetry, checks threshold,
    and generates instructor alerts if threshold is reached.
    """
    records = scan_student_records(student_dir)
    clusters = aggregate_cohort_telemetry(records, student_dir=student_dir)
    breached = check_escalation_threshold(clusters, threshold=threshold)

    if not breached:
        return None

    latest_report: Optional[ProfessorEscalationReport] = None
    for cluster in breached:
        report, _ = generate_instructor_alert(cluster, call_llm=call_llm)

        if ctx is not None and hasattr(ctx, "append"):
            ctx.append(
                "escalation_report",
                report.model_dump(),
                produced_by="agent:batch_aggregator",
            )

        # --- send_email() when threshold is reached ---
        email_subject = (
            f"[CONCEPT GAP ALERT] {cluster.fallacy_tag} — "
            f"{cluster.occurrence_count} students affected"
        )
        student_list = ", ".join(cluster.affected_student_ids)
        sample_quotes = "\n".join(
            f"  - \"{q}\"" for q in cluster.sample_student_quotes[:3]
        )
        email_body = (
            f"Dear Professor,\n\n"
            f"Our Feynman Check system has detected a recurring misconception "
            f"across {cluster.occurrence_count} students.\n\n"
            f"Misconception: {cluster.fallacy_tag}\n"
            f"Affected Students: {student_list}\n\n"
            f"Sample Student Responses:\n{sample_quotes}\n\n"
            f"Suggested Remediation:\n{cluster.remediation_suggestion}\n\n"
            f"This alert was automatically generated when {cluster.occurrence_count} "
            f"or more students exhibited the same fallacy (threshold = {threshold}).\n\n"
            f"— Feynman Check Agent"
        )
        send_email(subject=email_subject, body=email_body)

        if interactive:
            report = escalate_to_professor(report, mode="cli")

        latest_report = report

    return latest_report


# ---------------------------------------------------------------------------
# 8. Complete Pipeline Runner
# ---------------------------------------------------------------------------

def run_batch_pipeline(
    records: Optional[List[StudentSessionRecord]] = None,
    student_dir: Path | str = DEFAULT_STUDENTS_DIR,
    reports_dir: Path | str = DEFAULT_REPORTS_DIR,
    threshold: int = BATCH_ALERT_THRESHOLD,
    action: Optional[str] = None,
    call_llm: Optional[Callable] = None,
) -> Tuple[Dict[str, BatchMisconceptionCluster], List[ProfessorEscalationReport]]:
    """
    Orchestrates the entire batch aggregation and escalation pipeline.
    """
    clusters = aggregate_cohort_telemetry(records, student_dir=student_dir)
    breached = check_escalation_threshold(clusters, threshold=threshold)

    reports: List[ProfessorEscalationReport] = []
    for cluster in breached:
        report, _ = generate_instructor_alert(
            cluster,
            reports_dir=reports_dir,
            call_llm=call_llm,
        )
        if action:
            report = escalate_to_professor(report, action=action)
        reports.append(report)

    return clusters, reports
