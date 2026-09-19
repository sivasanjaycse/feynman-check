"""
demo/feynman/discover.py — Fallacy Discovery Agent.

Analyzes a lecture / concept markdown file and autonomously identifies
common student misconceptions (fallacies), example flawed claims,
pedagogical counters, and an opening diagnostic question.

Can format and write the discovered fallacies directly back into the
concept .md file so downstream Socratic chat and batch aggregation
can use them automatically.

Usage:
    from demo.feynman.discover import discover_fallacies
    result = discover_fallacies("oop_lecture_1")                # live LLM
    result = discover_fallacies("oop_lecture_1", call=stub)      # offline stub
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from slice.budget import Budget
from slice.config import Settings, settings as load_settings
from slice.llm import complete
from slice.store import Store

from .schema import ConceptFallacies, DiscoveredFallacy


_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "concepts"
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_discover_prompt_template() -> str:
    """Load the fallacy discovery prompt template."""
    prompt_file = _PROMPTS_DIR / "discover_fallacies.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return (
        "You are an expert computer science educator. Given the ground-truth invariants, "
        "lecture notes, and transcript for a concept, identify 3 common student misconceptions "
        "and an opening diagnostic question. Return structured ConceptFallacies JSON."
    )


def extract_concept_content(concept_id: str, concepts_dir: Path | str = _DATA_DIR) -> tuple[str, str, Path]:
    """Read concept file and return (full_content, content_without_section_2, file_path).

    Strips any existing '## 2. Common Fallacy Patterns' so the model
    analyzes only the invariants, lecture notes, and transcripts.
    """
    cdir = Path(concepts_dir)
    md_file = cdir / f"{concept_id}.md"
    if not md_file.exists():
        candidates = list(cdir.glob(f"*{concept_id}*.md"))
        if candidates:
            md_file = candidates[0]
        else:
            raise FileNotFoundError(f"Concept file not found: {md_file}")

    content = md_file.read_text(encoding="utf-8")

    # Strip existing Section 2 if present
    stripped = re.sub(
        r"\n## 2\. Common Fallacy Patterns.*?(?=\n## |\Z)",
        "",
        content,
        flags=re.DOTALL,
    ).strip()

    return content, stripped, md_file


def has_existing_fallacies(content: str) -> bool:
    """Check if the concept markdown already contains a Section 2."""
    return bool(re.search(r"## 2\. Common Fallacy Patterns", content))


def format_fallacies_markdown(fallacies: list[DiscoveredFallacy]) -> str:
    """Format discovered fallacies into the standard markdown format
    expected by load_concept_fallacies_from_markdown()."""
    lines = [
        "## 2. Common Fallacy Patterns (Known Misconceptions)",
        "",
    ]
    for f in fallacies:
        tag = f.tag.strip().replace(" ", "_").upper()
        lines.append(f"### `{tag}`")
        lines.append(f"- **Description:** {f.description.strip()}")
        lines.append(f"- **Example flawed claim:** *{f.example_claim.strip()}*")
        lines.append(f"- **Pedagogical counter:** {f.pedagogical_counter.strip()}")
        lines.append("")
    return "\n".join(lines).strip()


def write_fallacies_to_file(
    md_file: Path,
    fallacies_md: str,
    opening_question: Optional[str] = None,
) -> None:
    """Writes the generated Section 2 (and optionally Section 5 opening question)
    into the concept file."""
    content = md_file.read_text(encoding="utf-8")

    # Remove existing Section 2 if present
    content = re.sub(
        r"\n## 2\. Common Fallacy Patterns.*?(?=\n## |\Z)",
        "",
        content,
        flags=re.DOTALL,
    )

    # Insert Section 2 before Section 3, or before Section 4, or append
    inserted = False
    for next_section in [r"\n## 3\.", r"\n## 4\.", r"\n## 5\."]:
        match = re.search(next_section, content)
        if match:
            pos = match.start()
            content = content[:pos] + "\n\n---\n\n" + fallacies_md + content[pos:]
            inserted = True
            break

    if not inserted:
        content = content.rstrip() + "\n\n---\n\n" + fallacies_md + "\n"

    # Add or update Section 5 (Opening Question) if provided
    if opening_question and opening_question.strip():
        q_text = opening_question.strip()
        if "## 5. Opening Question" in content:
            content = re.sub(
                r"(## 5\. Opening Question\s*\n+)(.*?)(?=\n## |\Z)",
                rf"\g<1>{q_text}\n",
                content,
                flags=re.DOTALL,
            )
        else:
            content = content.rstrip() + f"\n\n---\n\n## 5. Opening Question\n\n{q_text}\n"

    md_file.write_text(content, encoding="utf-8")


def discover_fallacies(
    concept_id: str,
    *,
    call: Callable = complete,
    settings: Optional[Settings] = None,
    force: bool = False,
    write: bool = True,
    concepts_dir: Path | str = _DATA_DIR,
    db_path: str = "demo.db",
) -> ConceptFallacies:
    """
    Fallacy Discovery Agent entry point.

    1. Loads the concept markdown file.
    2. If fallacies already exist and force=False, returns existing fallacies.
    3. Otherwise, strips Section 2 and sends content to LLM with the discover prompt.
    4. Validates output with ConceptFallacies Pydantic schema.
    5. Optionally writes Section 2 (and Section 5) back to the .md file.
    """
    st = settings or load_settings()
    full_content, stripped_content, md_file = extract_concept_content(concept_id, concepts_dir=concepts_dir)

    # If file already has fallacies and not forcing re-generation:
    if not force and has_existing_fallacies(full_content):
        from .batch import load_concept_fallacies_from_markdown
        existing = load_concept_fallacies_from_markdown(concept_id, concepts_dir=concepts_dir)
        if existing:
            fallacies = [
                DiscoveredFallacy(
                    tag=tag,
                    description=info.get("derailment", ""),
                    example_claim=info.get("example_claim", ""),
                    pedagogical_counter=info.get("pedagogical_counter", ""),
                )
                for tag, info in existing.items()
            ]
            from .flow import load_opening_question
            op_q = load_opening_question(concept_id)
            return ConceptFallacies(
                concept_id=concept_id,
                fallacies=fallacies,
                opening_question=op_q,
            )

    system_prompt = load_discover_prompt_template()
    user_prompt = (
        f"### CONCEPT TOPIC ID: {concept_id}\n\n"
        f"### LECTURE CONTENT & INVARIANTS:\n{stripped_content}\n\n"
        "Identify 3 distinct common student misconceptions (fallacies), provide an example flawed claim "
        "and a pedagogical Socratic counter for each, and suggest an opening diagnostic question."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    store = Store(db_path)
    run_id = store.create_run("fallacy_discovery", meta={"concept_id": concept_id})
    budget = Budget(store, run_id, st)

    try:
        result: ConceptFallacies = call(
            settings=st,
            budget=budget,
            messages=messages,
            schema=ConceptFallacies,
            step="discover_fallacies",
        )
    finally:
        store.close()

    if write:
        fallacies_md = format_fallacies_markdown(result.fallacies)
        write_fallacies_to_file(md_file, fallacies_md, result.opening_question)

    return result
