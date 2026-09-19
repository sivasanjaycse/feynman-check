"""
tests/test_discover_fallacies.py — Tests for the Fallacy Discovery Agent.

All tests run deterministically with zero live LLM token usage using StubCompleter.
"""
from __future__ import annotations

import pytest
from pathlib import Path

from demo.feynman.discover import (
    discover_fallacies,
    extract_concept_content,
    format_fallacies_markdown,
    has_existing_fallacies,
    write_fallacies_to_file,
)
from demo.feynman.schema import ConceptFallacies, DiscoveredFallacy
from demo.feynman.stub import StubCompleter
from demo.feynman.batch import load_concept_fallacies_from_markdown


class TestConceptExtraction:
    def test_extract_concept_content_strips_section_2(self):
        full, stripped, path = extract_concept_content("oop_lecture_1")
        assert "## 1. Ground Truth Invariants" in stripped
        assert "## 2. Common Fallacy Patterns" not in stripped
        assert "## 3. Lecture Notes" in stripped
        assert path.exists()

    def test_has_existing_fallacies_positive(self):
        full, _, _ = extract_concept_content("oop_lecture_1")
        assert has_existing_fallacies(full) is True

    def test_nonexistent_concept_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_concept_content("non_existent_topic_12345")


class TestMarkdownFormatting:
    def test_format_fallacies_markdown_structure(self):
        fallacies = [
            DiscoveredFallacy(
                tag="TEST_SAMPLE_FALLACY",
                description="Student thinks X is Y.",
                example_claim="X equals Y in all cases.",
                pedagogical_counter="If X were Y, what would happen in case Z?",
            ),
            DiscoveredFallacy(
                tag="ANOTHER_FALLACY",
                description="Student confuses A with B.",
                example_claim="A is basically B.",
                pedagogical_counter="A is compile time, B is runtime.",
            ),
        ]
        md = format_fallacies_markdown(fallacies)
        assert "## 2. Common Fallacy Patterns (Known Misconceptions)" in md
        assert "### `TEST_SAMPLE_FALLACY`" in md
        assert "- **Description:** Student thinks X is Y." in md
        assert "- **Example flawed claim:** *X equals Y in all cases.*" in md
        assert "- **Pedagogical counter:** If X were Y, what would happen in case Z?" in md
        assert "### `ANOTHER_FALLACY`" in md


class TestDiscoveryExecution:
    def test_discover_returns_existing_when_not_forced(self):
        """Without force=True, reads existing hand-curated fallacies without LLM call."""
        result = discover_fallacies(
            "oop_lecture_1",
            call=StubCompleter(),
            force=False,
            write=False,
        )
        assert isinstance(result, ConceptFallacies)
        assert result.concept_id == "oop_lecture_1"
        tags = [f.tag for f in result.fallacies]
        assert "CLASS_IS_AN_OBJECT" in tags

    def test_discover_forced_uses_stub_model(self):
        """With force=True, runs discovery agent (via StubCompleter) and yields newly identified fallacies."""
        stub = StubCompleter()
        result = discover_fallacies(
            "oop_lecture_1",
            call=stub,
            force=True,
            write=False,
        )
        assert isinstance(result, ConceptFallacies)
        assert len(result.fallacies) == 3
        tags = [f.tag for f in result.fallacies]
        assert "AUTONOMOUS_CONCEPT_CONFLATION" in tags

    def test_write_and_parse_roundtrip(self, tmp_path):
        """Tests that written markdown can be parsed back by the existing batch regex parser."""
        temp_concept = tmp_path / "temp_lecture.md"
        temp_concept.write_text(
            "# Lecture: Concurrency\n\n"
            "## 1. Ground Truth Invariants\n\n"
            "### Invariant 1: Locks\n- Mutual exclusion.\n\n"
            "## 3. Lecture Notes\n\nNotes about concurrency.\n",
            encoding="utf-8",
        )

        fallacies = [
            DiscoveredFallacy(
                tag="LOCK_FREE_MEANS_NO_SYNC",
                description="Student thinks lock-free means no synchronization.",
                example_claim="Lock-free algorithms don't need memory barriers.",
                pedagogical_counter="Atomic compare-and-swap still coordinates memory.",
            ),
        ]
        fallacies_md = format_fallacies_markdown(fallacies)
        write_fallacies_to_file(temp_concept, fallacies_md, opening_question="Hey! What is a lock?")

        parsed = load_concept_fallacies_from_markdown("temp_lecture", concepts_dir=tmp_path)
        assert "LOCK_FREE_MEANS_NO_SYNC" in parsed
        assert "Student thinks lock-free" in parsed["LOCK_FREE_MEANS_NO_SYNC"]["derailment"]
        assert "Atomic compare-and-swap" in parsed["LOCK_FREE_MEANS_NO_SYNC"]["pedagogical_counter"]
