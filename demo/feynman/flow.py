"""
demo/feynman/flow.py - The Socratic State Machine & Feynman Check Flow.

Orchestrates the interactive Socratic dialogue for evaluating student conceptual
explanations against ground-truth lecture invariants.

Core State Transitions:
  AWAIT_EXPLANATION (DRAFTING)
        │
        ▼
  CRITIC_EVALUATE (GATING)
        │
        ├─▶ MISCONCEPTION / AMBIGUOUS (and revisions < 2)
        │     │
        │     ▼
        │   SOCRATIC_PROBE (PROBING)
        │     │
        │     └─▶ [THE BACK-EDGE] ──▶ AWAIT_EXPLANATION
        │
        └─▶ MASTERED or revisions >= 2
              │
              ▼
            LOG_STUDENT_STATE ──▶ COMPLETE

Architectural Guarantees:
1. Orchestration in Python, judgement in the model (Principle 7).
2. The Back-Edge: Work flows backward to generate counter-examples rather than giving answers.
3. Bounded loops: Revision count strictly derived from record history (`ctx.history("verdict")`),
   never from LLM spend retry counters (`budget.attempt()`) (Principle 3).
4. Full auditability: All student explanations, critic verdicts, probes, and session records
   are durably appended to SQLite (Principle 1) and persisted to data/students/{student_id}.json.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

from slice.llm import complete
from slice.records import RunState
from slice.runner import Context

from .schema import (
    CriticVerdict,
    ProbeMessage,
    StudentSessionRecord,
    StudentSubmission,
)
from .stub import get_canned_student, INVARIANT_VIRTUAL_MEMORY

# ---------------------------------------------------------------------------
# State Aliases matching AgentSpec & TEAM_TASKS
# ---------------------------------------------------------------------------
AWAIT_EXPLANATION  = RunState.DRAFTING
CRITIC_EVALUATE    = RunState.GATING
SOCRATIC_PROBE     = RunState.PROBING
AWAITING_STUDENT   = RunState.AWAITING_EXPERT   # suspended: waiting for next web message
COMPLETE           = RunState.COMPLETE
FAILED             = RunState.FAILED

# ---------------------------------------------------------------------------
# Domain Bounds
# ---------------------------------------------------------------------------
MAX_REVISIONS = 2
"""
Maximum number of counter-example iterations allowed per student before escalation.
Derived strictly from len(ctx.history("verdict")) - NOT budget.attempt().
"""

# Path to ground truth invariants and prompt templates
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "concepts"
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


# ---------------------------------------------------------------------------
# Helpers: Ground Truth & Prompt Loading
# ---------------------------------------------------------------------------

def load_concept_ground_truth(concept_id: str = "oop_lecture_1") -> str:
    """Load the ground-truth markdown invariant file for a concept.

    Raises FileNotFoundError with a helpful message if the concept file
    is not found. Suggest similar concept IDs from data/concepts/ if available.
    """
    concept_file = _DATA_DIR / f"{concept_id}.md"
    if concept_file.exists():
        return concept_file.read_text(encoding="utf-8")

    # Try fuzzy match: find closest concept_id in data/concepts/
    available = [f.stem for f in _DATA_DIR.glob("*.md")] if _DATA_DIR.exists() else []
    suggestion = ""
    if available:
        # Simple prefix/substring suggestion
        matches = [a for a in available if concept_id in a or a in concept_id]
        if matches:
            suggestion = f" Did you mean: {matches[0]}?"
        else:
            suggestion = f" Available concepts: {', '.join(available)}."
    raise FileNotFoundError(
        f"Concept file not found: data/concepts/{concept_id}.md{suggestion}\n"
        f"Run: python scripts/feynman.py list-concepts"
    )



def load_prompt_template(name: str) -> str:
    """Load a markdown prompt template from demo/feynman/prompts/."""
    prompt_file = _PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Message Builders
# ---------------------------------------------------------------------------

def build_critic_messages(
    concept_ground_truth: str,
    student_text: str,
    concept_id: str = "oop_lecture_1",
    prior_verdicts: Optional[List[Dict[str, Any]]] = None,
    prior_probes: Optional[List[Dict[str, Any]]] = None,
    current_target_fallacy: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Builds prompt messages for the Critic evaluation step."""
    system_prompt = load_prompt_template("critic")

    user_sections = [
        f"### GROUND TRUTH CONCEPT INVARIANTS:\nconcept_id: {concept_id}\n{concept_ground_truth}",
    ]

    if prior_verdicts and prior_probes:
        history_lines = []
        for i, (v, p) in enumerate(zip(prior_verdicts, prior_probes)):
            history_lines.append(
                f"- Round {i+1}:\n"
                f"  Critic Verdict: {v.get('verdict')} (Flaw: {v.get('detected_flaw_tag')})\n"
                f"  Socratic Probe Issued: {p.get('counter_example_scenario')}"
            )
        user_sections.append("### PRIOR INTERACTION HISTORY:\n" + "\n".join(history_lines))

    if current_target_fallacy:
        user_sections.append(
            f"### CURRENT TARGET CONCEPT / POTENTIAL FALLACY BEING EVALUATED:\n`{current_target_fallacy}`\n"
            f"Check specifically if the student understands this concept or exhibits the `{current_target_fallacy}` misconception."
        )

    user_sections.append(
        f"### STUDENT SUBMISSION TO EVALUATE:\n\"{student_text}\"\n\n"
        "Evaluate this submission against the ground truth invariants above. "
        "Catch semantic conflations, missing distinctions, or violations of the stated invariants. "
        "Return a structured CriticVerdict."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n---\n\n".join(user_sections)},
    ]


def build_probe_messages(
    concept_ground_truth: str,
    student_text: str,
    verdict: Dict[str, Any],
    concept_id: str = "oop_lecture_1",
    target_fallacy: Optional[str] = None,
    upcoming_fallacy_info: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Builds prompt messages for the Socratic counter-example generator."""
    system_prompt = load_prompt_template("probe")

    is_mastered_transition = verdict.get("verdict") == "MASTERED"

    user_sections = [
        f"### GROUND TRUTH CONCEPT INVARIANTS:\nconcept_id: {concept_id}\n{concept_ground_truth}",
    ]

    if is_mastered_transition and upcoming_fallacy_info:
        tag = upcoming_fallacy_info.get("tag") or target_fallacy or "NEXT_CONCEPT"
        title = upcoming_fallacy_info.get("title", tag)
        desc = upcoming_fallacy_info.get("derailment", "")
        counter = upcoming_fallacy_info.get("pedagogical_counter", "")
        example_claim = upcoming_fallacy_info.get("example_claim", "")

        user_sections.append(
            f"### PREVIOUS STUDENT ANSWER (CORRECT):\n\"{student_text}\"\n\n"
            f"The student demonstrated solid understanding on the previous topic!\n"
            f"Now, progress the revision to the UPCOMING FALLACY from this lecture:\n"
            f"- Target Fallacy to test: `{tag}` ({title})\n"
            f"- Fallacy description: {desc}\n"
            f"- Example flawed student belief: \"{example_claim}\"\n"
            f"- Pedagogical counter context: \"{counter}\"\n\n"
            "Rules for your response:\n"
            "1. In your first sentence, briefly acknowledge and praise their previous correct answer.\n"
            f"2. Then present a realistic programming scenario or question that directly tests whether the student holds the `{tag}` misconception.\n"
            "3. Do NOT give away the invariant or explain the answer.\n"
            f"4. Keep the entire response under 70 words. Return a structured ProbeMessage with target_invariant set to '{tag}'."
        )
    elif is_mastered_transition:
        user_sections.append(
            f"### PREVIOUS STUDENT ANSWER (CORRECT):\n\"{student_text}\"\n\n"
            "The student answered the previous question correctly! "
            "Now, test them on ANOTHER common fallacy or invariant from the GROUND TRUTH section above "
            "that has NOT been tested yet.\n"
            "Rules:\n"
            "1. Briefly acknowledge their correct answer in ONE short sentence.\n"
            "2. Select a DIFFERENT common fallacy from the GROUND TRUTH section.\n"
            "3. Ask ONE clear diagnostic question that tests whether the student holds that misconception.\n"
            "4. Keep the total response under 70 words. Return a structured ProbeMessage."
        )
    else:
        user_sections.extend([
            f"### STUDENT SUBMISSION (CONTAINING MISCONCEPTION):\n\"{student_text}\"",
            f"### CRITIC DIAGNOSIS:\n"
            f"- Flaw Tag: {verdict.get('detected_flaw_tag')}\n"
            f"- Flaw Explanation: {verdict.get('flaw_explanation')}\n"
            f"- Confidence: {verdict.get('confidence')}",
            "Generate a concrete edge-case counter-example probe that forces the student "
            "to confront their faulty assumption without directly giving away the invariant. "
            "Keep the response under 70 words. Return a structured ProbeMessage."
        ])

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n---\n\n".join(user_sections)},
    ]


# ---------------------------------------------------------------------------
# Telemetry Persistence: Log Student State
# ---------------------------------------------------------------------------

def log_student_session_state(
    ctx: Context,
    final_verdict: str,
) -> StudentSessionRecord:
    """
    Serializes completed session telemetry to the Store and to local JSON
    under data/students/{student_id}.json.
    """
    submissions = [s.payload for s in ctx.history("submission")]
    probes = [p.payload for p in ctx.history("probe")]
    verdicts = [v.payload for v in ctx.history("verdict")]

    initial_submission = submissions[0] if submissions else {}
    student_id = initial_submission.get("student_id") or ctx.store.meta(ctx.run_id).get("student_id", "2023101001")
    concept_id = initial_submission.get("concept_id", "oop_lecture_1")
    initial_text = initial_submission.get("text", "")

    student_revisions = [s.get("text", "") for s in submissions[1:]]
    probes_issued = [p.get("counter_example_scenario", "") for p in probes]

    # Tag initial fallacy detected, if any
    tagged_fallacy = None
    for v in verdicts:
        if v.get("detected_flaw_tag"):
            tagged_fallacy = v["detected_flaw_tag"]
            break

    session_record = StudentSessionRecord(
        student_id=str(student_id),
        concept_id=concept_id,
        iteration_count=len(probes_issued),
        initial_text=initial_text,
        probes_issued=probes_issued,
        student_revisions=student_revisions,
        final_verdict=final_verdict,  # type: ignore[arg-type]
        tagged_fallacy=tagged_fallacy,
    )

    # 1. Append to durable SQLite Store
    ctx.append("session_record", session_record.model_dump(), produced_by="agent:feynman_logger")

    # 2. Persist to local JSON file for Member 4 batch aggregator
    students_dir = Path("data/students")
    students_dir.mkdir(parents=True, exist_ok=True)
    out_file = students_dir / f"{student_id}.json"
    out_file.write_text(session_record.model_dump_json(indent=2), encoding="utf-8")

    # 3. Optional hook for batch aggregation check
    try:
        from .batch import check_and_escalate_batch  # type: ignore
        check_and_escalate_batch(ctx)
    except (ImportError, AttributeError):
        pass

    return session_record


# ---------------------------------------------------------------------------
# The Flow Factory
# ---------------------------------------------------------------------------

def build_flow(call: Callable = complete) -> SimpleNamespace:
    """
    Constructs the Feynman Check state machine flow.
    `call` is dependency-injected: defaults to live LLM `complete`,
    or accepts `stub_complete` for zero-token deterministic offline execution.
    """

    def handle_await_explanation(ctx: Context) -> RunState:
        """
        State: AWAIT_EXPLANATION (DRAFTING)
        Ingests the student's explanation (initial or revision) and routes to CRITIC_EVALUATE.
        """
        submissions = ctx.history("submission")
        probes = ctx.history("probe")
        meta = ctx.store.meta(ctx.run_id)

        # --------------------------------------------------------- Initial Submission
        if not submissions:
            # Check for initial input in store
            input_entry = ctx.latest("input")
            if input_entry:
                student_id = input_entry.get("student_id") or meta.get("student_id", "2023101001")
                concept_id = input_entry.get("concept_id") or meta.get("concept_id", "oop_lecture_1")
                text = input_entry.get("text", "")
            else:
                student_id = meta.get("student_id", "2023101001")
                concept_id = meta.get("concept_id", "oop_lecture_1")
                text = meta.get("text", "")

            ctx.append(
                "submission",
                {
                    "student_id": str(student_id),
                    "concept_id": concept_id,
                    "text": text,
                    "iteration": 0,
                },
                produced_by="student:initial",
            )
            return CRITIC_EVALUATE

        # --------------------------------------------------------- Back-Edge Revision
        # We returned to AWAIT_EXPLANATION because a SOCRATIC_PROBE was issued.
        # Check if a revision text was already supplied or if we can supply from canned/simulated profile.
        current_probe_count = len(probes)
        current_submission_count = len(submissions)

        if current_submission_count <= current_probe_count:
            # Need revision for the latest probe
            student_id = submissions[0].payload.get("student_id", "")
            student_name = meta.get("student_name") or student_id

            if meta.get("interactive"):
                latest_p = probes[-1].payload.get("counter_example_scenario", "")
                print(f"\n\033[35m+--- Socratic Counter-Probe -------------------------------------------+\033[0m")
                for line in textwrap.wrap(latest_p, width=74):
                    print(f"\033[35m|\033[0m {line}")
                print(f"\033[35m+---------------------------------------------------------------------+\033[0m\n")
                try:
                    revision_text = input("\033[1;36mHow do you revise your explanation? > \033[0m").strip()
                except (KeyboardInterrupt, EOFError):
                    revision_text = "Student declined to revise."
                if not revision_text:
                    revision_text = "Student submitted empty revision."
            else:
                canned = get_canned_student(student_name)
                if canned and canned.get("revision_text"):
                    revision_text = canned["revision_text"]
                else:
                    # Check meta for a queued revision
                    queued_revisions = meta.get("revisions", [])
                    rev_idx = current_probe_count - 1
                    if rev_idx < len(queued_revisions):
                        revision_text = queued_revisions[rev_idx]
                    else:
                        # In simulated or headless runs without interactive input, fall back to canned or empty
                        revision_text = "Revised explanation acknowledging page table in RAM."

            ctx.append(
                "submission",
                {
                    "student_id": str(student_id),
                    "concept_id": submissions[0].payload.get("concept_id", "oop_lecture_1"),
                    "text": revision_text,
                    "iteration": current_probe_count,
                },
                produced_by="student:revision",
            )

        return CRITIC_EVALUATE

    def handle_critic_evaluate(ctx: Context) -> RunState:
        """
        State: CRITIC_EVALUATE (GATING)
        Evaluates the student explanation against ground truth invariants.
        Routes to SOCRATIC_PROBE (Back-Edge) if flawed, or LOG_STUDENT_STATE if mastered / bounded.
        """
        latest_sub = ctx.latest("submission")
        if not latest_sub:
            ctx.append("failure", {"kind": "missing_submission", "detail": "No student submission found"}, produced_by="runner")
            return FAILED

        concept_id = latest_sub.get("concept_id", "oop_lecture_1")
        ground_truth = load_concept_ground_truth(concept_id)

        prior_verdicts = [v.payload for v in ctx.history("verdict")]
        prior_probes = [p.payload for p in ctx.history("probe")]

        # Call Critic agent
        messages = build_critic_messages(
            concept_ground_truth=ground_truth,
            student_text=latest_sub.get("text", ""),
            concept_id=concept_id,
            prior_verdicts=prior_verdicts,
            prior_probes=prior_probes,
        )

        verdict: CriticVerdict = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=messages,
            schema=CriticVerdict,
            step="critic",
        )

        ctx.append("verdict", verdict.model_dump(), produced_by="agent:critic")

        # --------------------------------------------------------- Mastered Case
        if verdict.verdict == "MASTERED":
            log_student_session_state(ctx, final_verdict="MASTERED")
            return COMPLETE

        # --------------------------------------------------------- Misconception / Ambiguous Case
        # Count revisions strictly from verdict history count
        # (prior_verdicts has verdicts BEFORE this one; so len(prior_verdicts) is the revision index)
        revision_attempts = len(prior_verdicts)

        if revision_attempts < MAX_REVISIONS:
            # Work goes backward: generate a Socratic probe!
            return SOCRATIC_PROBE

        # Reached revision bound (>= 2 iterations without mastering)
        # Escalates as unresolved
        log_student_session_state(ctx, final_verdict="UNRESOLVED_ESCALATE")
        return COMPLETE

    def handle_socratic_probe(ctx: Context) -> RunState:
        """
        State: SOCRATIC_PROBE (PROBING)
        Constructs a targeted counter-example scenario exposing the student's misconception.
        Transitions BACKWARD to AWAIT_EXPLANATION (The Back-Edge).
        """
        latest_sub = ctx.latest("submission")
        latest_verdict = ctx.latest("verdict")
        concept_id = latest_sub.get("concept_id", "oop_lecture_1") if latest_sub else "oop_lecture_1"
        ground_truth = load_concept_ground_truth(concept_id)

        messages = build_probe_messages(
            concept_ground_truth=ground_truth,
            student_text=latest_sub.get("text", "") if latest_sub else "",
            verdict=latest_verdict or {},
            concept_id=concept_id,
        )

        probe: ProbeMessage = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=messages,
            schema=ProbeMessage,
            step="probe",
        )

        ctx.append("probe", probe.model_dump(), produced_by="agent:socratic_tutor")

        # The Back-Edge: Work transitions backward to AWAIT_EXPLANATION
        return AWAIT_EXPLANATION

    return SimpleNamespace(
        name="feynman",
        handlers={
            AWAIT_EXPLANATION: handle_await_explanation,
            CRITIC_EVALUATE:   handle_critic_evaluate,
            SOCRATIC_PROBE:    handle_socratic_probe,
        },
    )


# ---------------------------------------------------------------------------
# Web Chat Flow Factory
# ---------------------------------------------------------------------------

MAX_CHAT_REVISIONS = 4
"""Maximum revision rounds in the web chat flow (more conversational)."""


def load_opening_question(concept_id: str) -> str:
    """Load the hardcoded opening question from a concept markdown file.

    Looks for a '## 5. Opening Question' section in the concept file.
    Falls back to a generic opener if not found.
    """
    import re
    concept_file = _DATA_DIR / f"{concept_id}.md"
    if not concept_file.exists():
        return f"Hey! Tell me what you understand about {concept_id.replace('_', ' ')}."

    content = concept_file.read_text(encoding="utf-8")
    # Look for ## 5. Opening Question section
    match = re.search(
        r"##\s*5\.\s*Opening Question\s*\n+(.*?)(?:\n##|\Z)",
        content,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return f"Hey! Tell me what you understand about {concept_id.replace('_', ' ')}."


def build_chat_flow(call: Callable = complete) -> SimpleNamespace:
    """
    Constructs a web-optimized Feynman Check flow for the chat UI.

    Key differences from build_flow():
    - No stdin/input() calls — student text is pre-appended to the Store by the web API
    - Higher revision limit (MAX_CHAT_REVISIONS) for more conversational depth
    - Returns after each state transition so the web API can return intermediate results
    """

    def handle_await_explanation(ctx: Context) -> RunState:
        """
        Web variant: reads student message from the Store history of 'chat_message'.
        Ensures each student message is consumed exactly once per turn.
        """
        submissions = ctx.history("submission")
        chat_messages = ctx.history("chat_message")
        meta = ctx.store.meta(ctx.run_id)

        current_submission_count = len(submissions)

        # If no new message has been posted for this turn, suspend
        if current_submission_count >= len(chat_messages):
            return AWAITING_STUDENT

        student_msg = chat_messages[current_submission_count].payload
        text = student_msg.get("text", "").strip()
        student_id = student_msg.get("student_id") or meta.get("student_id", "anonymous")
        concept_id = meta.get("concept_id", "oop_lecture_1")

        ctx.append(
            "submission",
            {
                "student_id": str(student_id),
                "concept_id": concept_id,
                "text": text,
                "iteration": current_submission_count,
            },
            produced_by="student:initial" if current_submission_count == 0 else "student:revision",
        )
        return CRITIC_EVALUATE

    def handle_critic_evaluate(ctx: Context) -> RunState:
        """Evaluates student explanation against ground truth and manages multi-fallacy progression."""
        latest_sub = ctx.latest("submission")
        if not latest_sub:
            ctx.append("failure", {"kind": "missing_submission", "detail": "No student submission found"}, produced_by="runner")
            return FAILED

        concept_id = latest_sub.get("concept_id", "oop_lecture_1")
        ground_truth = load_concept_ground_truth(concept_id)

        from .batch import load_concept_fallacies_from_markdown
        fallacies_map = load_concept_fallacies_from_markdown(concept_id)
        all_fallacies = list(fallacies_map.keys())
        if not all_fallacies:
            all_fallacies = ["CORE_CONCEPT_INVARIANT"]

        prior_verdicts = [v.payload for v in ctx.history("verdict")]
        prior_probes = [p.payload for p in ctx.history("probe")]

        # Determine which fallacy was targeted for this submission
        # Submission 0 was tested on all_fallacies[0] (Opening Question)
        current_target_fallacy = all_fallacies[0]
        if prior_probes:
            current_target_fallacy = prior_probes[-1].get("target_fallacy") or all_fallacies[0]

        messages = build_critic_messages(
            concept_ground_truth=ground_truth,
            student_text=latest_sub.get("text", ""),
            concept_id=concept_id,
            prior_verdicts=prior_verdicts,
            prior_probes=prior_probes,
            current_target_fallacy=current_target_fallacy,
        )

        verdict: CriticVerdict = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=messages,
            schema=CriticVerdict,
            step="critic",
        )

        ctx.append("verdict", verdict.model_dump(), produced_by="agent:critic")

        # Track which fallacies have been mastered so far
        all_verdicts = [v.payload for v in ctx.history("verdict")]
        mastered_fallacies = []
        for i, v in enumerate(all_verdicts):
            target = all_fallacies[0]
            if i > 0 and (i - 1) < len(prior_probes):
                target = prior_probes[i - 1].get("target_fallacy") or target
            elif i == len(all_verdicts) - 1:
                target = current_target_fallacy
            if v.get("verdict") == "MASTERED" and target not in mastered_fallacies:
                mastered_fallacies.append(target)

        # What fallacies from this lecture have NOT been mastered yet?
        upcoming_fallacies = [f for f in all_fallacies if f not in mastered_fallacies]

        # Case 1: Student answer was MASTERED
        if verdict.verdict == "MASTERED":
            # If there are still upcoming fallacies to test and we haven't reached session bound:
            if upcoming_fallacies and len(all_verdicts) < MAX_CHAT_REVISIONS:
                return SOCRATIC_PROBE
            else:
                log_student_session_state(ctx, final_verdict="MASTERED")
                return COMPLETE

        # Case 2: MISCONCEPTION or AMBIGUOUS
        # Check attempts on current fallacy
        attempts_on_current = 1
        for i in range(len(prior_verdicts) - 1, -1, -1):
            prev_target = all_fallacies[0]
            if i > 0 and (i - 1) < len(prior_probes):
                prev_target = prior_probes[i - 1].get("target_fallacy") or prev_target
            if prev_target == current_target_fallacy:
                attempts_on_current += 1
            else:
                break

        # If student has had 2 attempts on this fallacy and there are upcoming fallacies:
        # Progress to the upcoming fallacy so they aren't stuck forever on 1 question
        if attempts_on_current >= 2 and len(upcoming_fallacies) > 1 and len(all_verdicts) < MAX_CHAT_REVISIONS:
            return SOCRATIC_PROBE

        # Otherwise continue probing the current fallacy up to MAX_CHAT_REVISIONS
        if len(all_verdicts) < MAX_CHAT_REVISIONS:
            return SOCRATIC_PROBE

        log_student_session_state(ctx, final_verdict="UNRESOLVED_ESCALATE")
        return COMPLETE

    def handle_socratic_probe(ctx: Context) -> RunState:
        """Generate Socratic probe targeting current or upcoming lecture fallacy."""
        latest_sub = ctx.latest("submission")
        latest_verdict = ctx.latest("verdict")
        concept_id = latest_sub.get("concept_id", "oop_lecture_1") if latest_sub else "oop_lecture_1"
        ground_truth = load_concept_ground_truth(concept_id)

        from .batch import load_concept_fallacies_from_markdown
        fallacies_map = load_concept_fallacies_from_markdown(concept_id)
        all_fallacies = list(fallacies_map.keys())
        if not all_fallacies:
            all_fallacies = ["CORE_CONCEPT_INVARIANT"]

        prior_probes = [p.payload for p in ctx.history("probe")]
        all_verdicts = [v.payload for v in ctx.history("verdict")]

        mastered_fallacies = []
        for i, v in enumerate(all_verdicts):
            target = all_fallacies[0]
            if i > 0 and (i - 1) < len(prior_probes):
                target = prior_probes[i - 1].get("target_fallacy") or target
            if v.get("verdict") == "MASTERED" and target not in mastered_fallacies:
                mastered_fallacies.append(target)

        upcoming_fallacies = [f for f in all_fallacies if f not in mastered_fallacies]
        is_mastered = latest_verdict.get("verdict") == "MASTERED" if latest_verdict else False

        if is_mastered and upcoming_fallacies:
            next_target_fallacy = upcoming_fallacies[0]
            upcoming_info = fallacies_map.get(next_target_fallacy, {})
            upcoming_info["tag"] = next_target_fallacy
        else:
            next_target_fallacy = all_fallacies[0]
            if prior_probes:
                next_target_fallacy = prior_probes[-1].get("target_fallacy") or next_target_fallacy
            upcoming_info = {}

        messages = build_probe_messages(
            concept_ground_truth=ground_truth,
            student_text=latest_sub.get("text", "") if latest_sub else "",
            verdict=latest_verdict or {},
            concept_id=concept_id,
            target_fallacy=next_target_fallacy,
            upcoming_fallacy_info=upcoming_info,
        )

        probe: ProbeMessage = call(
            settings=ctx.settings,
            budget=ctx.budget,
            messages=messages,
            schema=ProbeMessage,
            step="probe",
        )

        probe_dict = probe.model_dump()
        probe_dict["target_fallacy"] = next_target_fallacy
        ctx.append("probe", probe_dict, produced_by="agent:socratic_tutor")

        # Suspend: yield control back to web API
        return AWAITING_STUDENT

    def handle_awaiting_student(ctx: Context) -> RunState:
        """State: AWAITING_STUDENT (AWAITING_EXPERT)"""
        return AWAIT_EXPLANATION

    return SimpleNamespace(
        name="feynman_chat",
        handlers={
            AWAIT_EXPLANATION: handle_await_explanation,
            CRITIC_EVALUATE:   handle_critic_evaluate,
            SOCRATIC_PROBE:    handle_socratic_probe,
            AWAITING_STUDENT:  handle_awaiting_student,
        },
    )

