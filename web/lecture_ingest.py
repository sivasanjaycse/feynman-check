"""
web/lecture_ingest.py — Lecture Ingestion Pipeline.

Converts an uploaded PDF or PPTX file into a structured concept markdown file
compatible with the Feynman Check Socratic agents.

Pipeline:
  1. Extract raw text from PDF (pypdf) or PPTX (python-pptx)
  2. Send raw text to LLM → generate structured concept .md
     (Ground Truth Invariants + Lecture Notes + Transcript sections)
  3. Write .md to data/concepts/<concept_id>.md
  4. Run Fallacy Discovery Agent (discover_fallacies) → populates Section 2
     (Common Fallacies) and Section 5 (Opening Question) directly into .md
  5. Register the lecture in data/lectures_registry.json

Usage (from app.py):
    from web.lecture_ingest import ingest_lecture
    result = ingest_lecture(file_bytes, filename, title, description)
"""
from __future__ import annotations

import json
import re
import textwrap
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
_CONCEPTS_DIR = _ROOT / "data" / "concepts"
_REGISTRY_PATH = _ROOT / "data" / "lectures_registry.json"


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf is not installed. Run: pip install pypdf")

    reader = PdfReader(BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {i + 1}]\n{text.strip()}")
    return "\n\n".join(pages)


def extract_text_from_pptx(file_bytes: bytes) -> str:
    """Extract all text from a PPTX file using python-pptx."""
    try:
        from pptx import Presentation
    except ImportError:
        raise RuntimeError("python-pptx is not installed. Run: pip install python-pptx")

    prs = Presentation(BytesIO(file_bytes))
    slides = []
    for i, slide in enumerate(prs.slides):
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text.strip())
        if texts:
            slides.append(f"[Slide {i + 1}]\n" + "\n".join(texts))
    return "\n\n".join(slides)


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in (".pptx", ".ppt"):
        if ext == ".ppt":
            # Inform user if legacy .ppt is passed
            try:
                return extract_text_from_pptx(file_bytes)
            except Exception as e:
                raise ValueError(
                    "Legacy .ppt binary files are not natively supported. "
                    "Please save as .pptx or .pdf and upload again."
                ) from e
        return extract_text_from_pptx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: '{ext}'. Only .pdf and .pptx are supported.")


# ---------------------------------------------------------------------------
# Helper: Slugification and Unique ID
# ---------------------------------------------------------------------------

def slugify_title(title: str) -> str:
    """Generate a lowercase url/identifier safe slug from a title."""
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "lecture"


def generate_unique_concept_id(title: str, registry: Optional[List[Dict[str, Any]]] = None) -> str:
    """Generate an unused concept_id derived from the title."""
    base = slugify_title(title)
    if registry is None:
        registry = load_registry()
    existing_ids = {lec["id"] for lec in registry}

    candidate = base
    suffix = 2
    while candidate in existing_ids or (_CONCEPTS_DIR / f"{candidate}.md").exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


# ---------------------------------------------------------------------------
# Concept MD Generation (LLM)
# ---------------------------------------------------------------------------

_CONCEPT_GEN_SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert computer science educator and curriculum designer.

    You will be given raw text extracted from a lecture slide deck or PDF notes.
    Your task is to convert this raw content into a structured Feynman Check
    concept markdown file.

    The output MUST follow this exact structure:

    ---
    # <Lecture Title>

    **Course:** <course name if mentioned, else "Computer Science">
    **Department:** <department if mentioned, else "Computer Science & Engineering">

    ---

    ## 1. Ground Truth Invariants

    List 3–5 core, precise invariants that a student MUST understand.
    Each invariant should be a specific factual statement, not vague.
    Format:
    ### Invariant N: <Name>
    - <bullet point facts explaining the strict guarantee, boundary condition, or invariant rule>

    ---

    ## 3. Lecture Notes

    A 2–4 paragraph prose summary of the key concepts, written as comprehensive study notes.
    Use **bold** for key terms and definitions.

    ---

    ## 4. Lecture Transcript (Excerpt)

    Write a 3–5 sentence mock transcript excerpt in the voice of a professor
    explaining the most important concept and invariant, starting with a quote mark.
    Format as a blockquote: > "..."

    ---

    Rules:
    - Be precise, rigorous, and technically accurate.
    - Do NOT add Section 2 (fallacies) — that is generated by the Fallacy Discovery Agent.
    - Do NOT add Section 5 (opening question) — that is generated by the Fallacy Discovery Agent.
    - Output ONLY the markdown content, no extra commentary or markdown fence blocks.
    - If the source text is short, use your expert computer science knowledge to expand on the topic.
""")


def _build_fallback_concept_md(title: str, description: str, raw_text: str) -> str:
    """Constructs a standard structured markdown file when LLM outputs non-standard text."""
    desc = description.strip() or f"Foundational concepts and invariants for {title}."
    sample_excerpt = raw_text[:400].replace("\n", " ").strip() if raw_text else desc

    return textwrap.dedent(f"""\
        # {title}

        **Course:** Computer Science
        **Department:** Computer Science & Engineering

        ---

        ## 1. Ground Truth Invariants

        ### Invariant 1: Core Mechanics of {title}
        - Foundational architectural guarantees established in {title}.
        - Operational semantics must maintain internal consistency under all state transitions.

        ### Invariant 2: Boundary Invariant and Structural Integrity
        - Edge conditions and lifecycle constraints must be rigorously enforced without side-effects.

        ### Invariant 3: Runtime Determinism
        - Contractual invariants cannot be bypassed or assumed away during execution.

        ---

        ## 3. Lecture Notes

        {desc}

        Key topics covered in this lecture include invariant verification, architectural boundaries,
        and preventing misconceptions during technical implementation.

        ---

        ## 4. Lecture Transcript (Excerpt)

        > "{sample_excerpt}"
    """)


def generate_concept_md(
    raw_text: str,
    concept_id: str,
    title: str,
    description: str,
    *,
    call: Optional[Callable] = None,
    db_path: str = "demo.db",
) -> str:
    """
    Call the LLM to convert raw PDF/PPTX text into a structured concept markdown.
    Uses slice.llm.complete() or a provided mock callable.
    """
    from slice.config import settings as load_settings
    from slice.llm import complete
    from slice.budget import Budget
    from slice.store import Store

    st = load_settings()
    llm_func = call or complete

    user_prompt = textwrap.dedent(f"""\
        Concept ID: {concept_id}
        Lecture Title: {title}
        Description: {description}

        === RAW LECTURE CONTENT (extracted from uploaded file) ===

        {raw_text[:12000]}

        ===

        Generate the structured concept markdown file now following the required format.
    """)

    messages = [
        {"role": "system", "content": _CONCEPT_GEN_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    store = Store(db_path)
    run_id = store.create_run("concept_generation", meta={"concept_id": concept_id})
    budget = Budget(store, run_id, st)

    try:
        raw_response = llm_func(
            settings=st,
            budget=budget,
            messages=messages,
            schema=None,   # free-form markdown output
            step="generate_concept_md",
        )
    finally:
        store.close()

    md_content = raw_response if isinstance(raw_response, str) else str(raw_response)

    # Strip any triple-backtick fences the model may have added
    md_content = re.sub(r"^```(?:markdown)?\s*\n", "", md_content.strip())
    md_content = re.sub(r"\n```\s*$", "", md_content.strip())

    # If the response doesn't have the standard invariants section, wrap with fallback structure
    if "## 1. Ground Truth Invariants" not in md_content:
        md_content = _build_fallback_concept_md(title, description, raw_text)

    return md_content.strip()


# ---------------------------------------------------------------------------
# Registry Management
# ---------------------------------------------------------------------------

def load_registry() -> list[dict]:
    """Load the lectures registry JSON. Returns [] if file doesn't exist."""
    if _REGISTRY_PATH.exists():
        try:
            return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_registry(lectures: list[dict]) -> None:
    """Persist the lectures registry JSON."""
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REGISTRY_PATH.write_text(
        json.dumps(lectures, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def register_lecture(concept_id: str, title: str, description: str) -> int:
    """
    Add a lecture to the registry if not already present.
    Returns the lecture number assigned.
    """
    lectures = load_registry()

    # Check for duplicate id
    for lec in lectures:
        if lec["id"] == concept_id:
            lec["title"] = title
            lec["desc"] = description
            save_registry(lectures)
            return lec["num"]

    num = max((lec["num"] for lec in lectures), default=0) + 1
    lectures.append({
        "id": concept_id,
        "num": num,
        "title": title,
        "desc": description,
    })
    save_registry(lectures)
    return num


def remove_lecture(concept_id: str) -> bool:
    """Remove a lecture from the registry. Returns True if found and removed."""
    lectures = load_registry()
    new_list = [lec for lec in lectures if lec["id"] != concept_id]
    if len(new_list) == len(lectures):
        return False
    save_registry(new_list)
    return True


# ---------------------------------------------------------------------------
# Ingest Result Container
# ---------------------------------------------------------------------------

class IngestResult:
    def __init__(
        self,
        concept_id: str,
        lecture_num: int,
        title: str,
        description: str,
        md_path: Path,
        raw_text_length: int,
        fallacies_count: int = 0,
        opening_question: str = "",
        fallacies: Optional[List[Dict[str, Any]]] = None,
    ):
        self.concept_id = concept_id
        self.lecture_num = lecture_num
        self.title = title
        self.description = description
        self.md_path = md_path
        self.raw_text_length = raw_text_length
        self.fallacies_count = fallacies_count
        self.opening_question = opening_question
        self.fallacies = fallacies or []


# ---------------------------------------------------------------------------
# Main Ingest Entry Point
# ---------------------------------------------------------------------------

def ingest_lecture(
    file_bytes: bytes,
    filename: str,
    title: str,
    description: str = "",
    concept_id: Optional[str] = None,
    *,
    run_discovery: bool = True,
    call: Optional[Callable] = None,
    db_path: str = "demo.db",
) -> IngestResult:
    """
    Full ingestion pipeline:
      1. Extract raw text from PDF/PPTX
      2. Generate structured concept markdown via LLM
      3. Write to data/concepts/<concept_id>.md
      4. Run Fallacy Discovery Agent ("run discovery") to populate Section 2
         (common fallacies) and Section 5 (opening diagnostic question) directly
         into the concept markdown file
      5. Register in data/lectures_registry.json so the new lecture appears on
         student dashboard and is immediately accessible for Socratic revision

    Raises:
        ValueError: unsupported file type or empty extracted text
        RuntimeError: missing library (pypdf / python-pptx)
    """
    # 1. Extract raw text
    raw_text = extract_text(file_bytes, filename)
    if not raw_text.strip():
        raise ValueError(
            "Could not extract any text from the uploaded file. "
            "The file may be image-only, password protected, or empty."
        )

    # Clean concept_id or auto-generate unique slug
    if concept_id and concept_id.strip():
        cid = re.sub(r"[^a-zA-Z0-9_]+", "_", concept_id.strip()).strip("_").lower()
    else:
        cid = generate_unique_concept_id(title)

    desc = description.strip() or f"Key invariants and concepts for {title}."

    # 2. Generate initial concept markdown (Invariants + Notes + Transcript)
    md_content = generate_concept_md(
        raw_text,
        concept_id=cid,
        title=title,
        description=desc,
        call=call,
        db_path=db_path,
    )

    # 3. Write initial markdown to data/concepts/
    _CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = _CONCEPTS_DIR / f"{cid}.md"
    md_path.write_text(md_content, encoding="utf-8")

    # 4. Fallacy Discovery Agent:
    # "run discovery" is ran to get the Fallacy Discovery Agent to create Section 2 and Section 5
    fallacies_list: List[Dict[str, Any]] = []
    opening_question = ""
    if run_discovery:
        from demo.feynman.discover import discover_fallacies
        from slice.llm import complete

        disc_call = call or complete
        disc_result = discover_fallacies(
            cid,
            call=disc_call,
            force=True,
            write=True,
            concepts_dir=_CONCEPTS_DIR,
            db_path=db_path,
        )
        fallacies_list = [f.model_dump() for f in disc_result.fallacies]
        opening_question = disc_result.opening_question or ""

    # 5. Register in lectures registry
    lecture_num = register_lecture(cid, title, desc)

    return IngestResult(
        concept_id=cid,
        lecture_num=lecture_num,
        title=title,
        description=desc,
        md_path=md_path,
        raw_text_length=len(raw_text),
        fallacies_count=len(fallacies_list),
        opening_question=opening_question,
        fallacies=fallacies_list,
    )
