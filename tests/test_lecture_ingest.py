"""
tests/test_lecture_ingest.py — Tests for Lecture Ingestion & Dynamic Registry.

Verifies:
  1. PDF text extraction via pypdf
  2. PPTX text extraction via python-pptx
  3. Format dispatching & validation
  4. Auto-slugification and unique ID generation
  5. Fallback structured concept generation
  6. End-to-end ingestion pipeline with Fallacy Discovery Agent execution
  7. FastAPI routes: GET /api/lectures, POST /instructor/upload-lecture
  8. Downstream student Socratic chat integration with new concept
"""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from pptx import Presentation
from pptx.util import Inches

from demo.feynman.stub import StubCompleter
from web.app import app, DB_PATH
from web.lecture_ingest import (
    extract_text,
    extract_text_from_pdf,
    extract_text_from_pptx,
    generate_concept_md,
    generate_unique_concept_id,
    ingest_lecture,
    load_registry,
    register_lecture,
    remove_lecture,
    slugify_title,
    _CONCEPTS_DIR,
    _REGISTRY_PATH,
)


# ---------------------------------------------------------------------------
# Test Helpers: Synthetic Documents
# ---------------------------------------------------------------------------

def create_sample_pdf_bytes(text: str = "Tree Traversal: Inorder, Preorder, Postorder") -> bytes:
    """Create a minimal valid single-page PDF with text stream in memory."""
    stream_content = f"BT /F1 18 Tf 50 700 Td ({text}) Tj ET".encode("latin-1")
    length = len(stream_content)
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        b"4 0 obj << /Length " + str(length).encode() + b" >> stream\n"
        + stream_content + b"\nendstream endobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n500\n%%EOF"
    )
    return pdf


def create_sample_pptx_bytes(text: str = "Binary Search Tree Invariants and Rotation Mechanisms") -> bytes:
    """Create a minimal single-slide PPTX with text in memory."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    tx_box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(2))
    tx_box.text_frame.text = text
    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests: Text Extraction
# ---------------------------------------------------------------------------

class TestExtraction:
    def test_extract_text_from_pdf(self):
        pdf_bytes = create_sample_pdf_bytes("Fundamental Invariant of Binary Trees")
        text = extract_text_from_pdf(pdf_bytes)
        assert "Binary Trees" in text
        assert "[Page 1]" in text

    def test_extract_text_from_pptx(self):
        pptx_bytes = create_sample_pptx_bytes("AVL Trees: Balance Factor and Left-Right Rotation")
        text = extract_text_from_pptx(pptx_bytes)
        assert "AVL Trees" in text
        assert "[Slide 1]" in text

    def test_extract_text_dispatch(self):
        pdf_bytes = create_sample_pdf_bytes("Testing PDF Dispatch")
        text_pdf = extract_text(pdf_bytes, "notes.pdf")
        assert "Testing PDF Dispatch" in text_pdf

        pptx_bytes = create_sample_pptx_bytes("Testing PPTX Dispatch")
        text_pptx = extract_text(pptx_bytes, "deck.pptx")
        assert "Testing PPTX Dispatch" in text_pptx

    def test_unsupported_extension_raises(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(b"some content", "document.docx")


# ---------------------------------------------------------------------------
# Tests: Slugification and Unique ID
# ---------------------------------------------------------------------------

class TestSlugification:
    def test_slugify_title(self):
        assert slugify_title("Data Structures: BFS & DFS!") == "data_structures_bfs_dfs"
        assert slugify_title("   OOP Lecture 8   ") == "oop_lecture_8"
        assert slugify_title("???") == "lecture"

    def test_generate_unique_concept_id(self):
        mock_registry = [{"id": "graphs_intro", "num": 1, "title": "Graphs Intro", "desc": ""}]
        uid1 = generate_unique_concept_id("Graphs Intro", registry=mock_registry)
        assert uid1 == "graphs_intro_2"


# ---------------------------------------------------------------------------
# Tests: Concept Markdown Generation & Fallback
# ---------------------------------------------------------------------------

class TestConceptGeneration:
    def test_generate_concept_md_with_stub(self, tmp_path):
        stub = StubCompleter()
        md = generate_concept_md(
            raw_text="Graph representations using adjacency matrix and adjacency list.",
            concept_id="test_graphs",
            title="Graph Representations",
            description="Matrix vs List complexity",
            call=stub,
            db_path=str(tmp_path / "test.db"),
        )
        assert "## 1. Ground Truth Invariants" in md
        assert "## 3. Lecture Notes" in md
        assert "## 4. Lecture Transcript" in md
        assert "Graph Representations" in md


# ---------------------------------------------------------------------------
# Tests: End-to-End Ingestion Pipeline
# ---------------------------------------------------------------------------

class TestIngestPipeline:
    def test_ingest_lecture_creates_concept_and_runs_discovery(self, tmp_path):
        test_concept_id = "test_lecture_bst_flow"
        test_title = "BST and Self Balancing Trees"
        test_desc = "Binary Search Tree properties, rotations, and AVL balance."

        pptx_bytes = create_sample_pptx_bytes("BST Property: all keys in left subtree < root < all keys in right subtree.")
        stub = StubCompleter()

        try:
            result = ingest_lecture(
                file_bytes=pptx_bytes,
                filename="bst_slides.pptx",
                title=test_title,
                description=test_desc,
                concept_id=test_concept_id,
                run_discovery=True,
                call=stub,
                db_path=str(tmp_path / "pipeline.db"),
            )

            # Check IngestResult attributes
            assert result.concept_id == test_concept_id
            assert result.title == test_title
            assert result.fallacies_count == 3
            assert len(result.fallacies) == 3
            assert result.opening_question != ""

            # Check concept file on disk
            md_file = _CONCEPTS_DIR / f"{test_concept_id}.md"
            assert md_file.exists()
            content = md_file.read_text(encoding="utf-8")

            # Must contain invariants (Section 1)
            assert "## 1. Ground Truth Invariants" in content
            # Must contain fallacies populated by Fallacy Discovery Agent (Section 2)
            assert "## 2. Common Fallacy Patterns" in content
            # Must contain lecture notes (Section 3)
            assert "## 3. Lecture Notes" in content
            # Must contain opening question populated by Fallacy Discovery Agent (Section 5)
            assert "## 5. Opening Question" in content

            # Check registered in registry
            registry = load_registry()
            matched = [lec for lec in registry if lec["id"] == test_concept_id]
            assert len(matched) == 1
            assert matched[0]["title"] == test_title

        finally:
            # Cleanup
            md_file = _CONCEPTS_DIR / f"{test_concept_id}.md"
            if md_file.exists():
                md_file.unlink()
            remove_lecture(test_concept_id)


# ---------------------------------------------------------------------------
# Tests: FastAPI Endpoints & Student Access
# ---------------------------------------------------------------------------

class TestWebEndpoints:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_lectures_api(self, client):
        resp = client.get("/api/lectures")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 7
        assert any(lec["id"] == "oop_lecture_1" for lec in data)

    def test_upload_lecture_unauthorized(self, client):
        # Without instructor_auth cookie
        resp = client.post(
            "/instructor/upload-lecture",
            data={"title": "Test Title"},
            files={"file": ("test.pdf", b"%PDF-dummy", "application/pdf")},
        )
        assert resp.status_code == 401

    def test_upload_lecture_and_student_chat_access(self, client, monkeypatch):
        # Mock LLM call inside lecture_ingest with StubCompleter
        stub = StubCompleter()
        from web import lecture_ingest
        original_generate = lecture_ingest.generate_concept_md

        def mock_generate_concept_md(*args, **kwargs):
            kwargs["call"] = stub
            return original_generate(*args, **kwargs)

        monkeypatch.setattr(lecture_ingest, "generate_concept_md", mock_generate_concept_md)

        # Also mock discover_fallacies call
        from demo.feynman import discover
        original_discover = discover.discover_fallacies

        def mock_discover_fallacies(concept_id, **kwargs):
            kwargs["call"] = stub
            return original_discover(concept_id, **kwargs)

        monkeypatch.setattr(discover, "discover_fallacies", mock_discover_fallacies)

        test_cid = "test_dynamic_web_lecture"
        test_title = "Dynamic Web Ingestion Lecture"
        pptx_bytes = create_sample_pptx_bytes("Heaps and Priority Queues: min-heap invariant and sift-down.")

        try:
            # 1. Instructor uploads lecture
            client.cookies.set("instructor_auth", "authenticated")
            upload_resp = client.post(
                "/instructor/upload-lecture",
                data={
                    "title": test_title,
                    "description": "Binary Heap invariants",
                    "concept_id": test_cid,
                    "run_discovery": "true",
                },
                files={"file": ("heaps.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            )
            assert upload_resp.status_code == 200
            res_data = upload_resp.json()
            assert res_data["status"] == "success"
            assert res_data["concept_id"] == test_cid
            assert res_data["fallacies_count"] == 3
            assert res_data["opening_question"] != ""

            # 2. Verify dynamic GET /api/lectures contains it
            lectures_resp = client.get("/api/lectures")
            all_lectures = lectures_resp.json()
            assert any(lec["id"] == test_cid for lec in all_lectures)

            # 3. Student logs in and visits dashboard
            client.cookies.clear()
            client.cookies.set("student_roll", "2023101001")
            dash_resp = client.get("/dashboard")
            assert dash_resp.status_code == 200
            assert test_title in dash_resp.text
            assert f"card-{test_cid}" in dash_resp.text

            # 4. Student clicks into chat for the new lecture
            chat_resp = client.get(f"/chat/{test_cid}")
            assert chat_resp.status_code == 200
            assert test_title in chat_resp.text
            # Opening question from Fallacy Discovery must be present in the chat page
            assert res_data["opening_question"] in chat_resp.text

        finally:
            # Cleanup
            md_file = _CONCEPTS_DIR / f"{test_cid}.md"
            if md_file.exists():
                md_file.unlink()
            remove_lecture(test_cid)
