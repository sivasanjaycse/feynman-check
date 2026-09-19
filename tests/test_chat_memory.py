"""
tests/test_chat_memory.py — Tests for conversation history tracking and meta-query handling.
Runs completely offline with 0 live tokens using StubCompleter.
"""
from __future__ import annotations

import pytest
from slice.records import RunState
from slice.store import Store
from slice.config import settings as load_settings
from slice import runner

from demo.feynman.flow import (
    build_chat_flow,
    build_critic_messages,
    build_probe_messages,
    format_dialogue_transcript,
    load_opening_question,
)
from demo.feynman.stub import StubCompleter


class TestTranscriptFormatting:
    def test_format_dialogue_transcript_ordering(self):
        submissions = [
            {"text": "A class is an object."},
            {"text": "What was the first question?"},
        ]
        probes = [
            {"counter_example_scenario": "If class Dog is an object, how many dogs exist before new Dog()?"},
        ]
        opening_q = "Hey! Explain what a class is and how it differs from an object."

        transcript = format_dialogue_transcript(
            submissions=submissions,
            probes=probes,
            opening_question=opening_q,
        )

        assert "Tutor (Opening Question): \"Hey! Explain what a class is" in transcript
        assert "Student: \"A class is an object.\"" in transcript
        assert "Tutor (Follow-up Question): \"If class Dog is an object" in transcript
        assert "Student: \"What was the first question?\"" in transcript


class TestPromptBuildersWithHistory:
    def test_critic_messages_include_transcript(self):
        transcript = "Tutor: Question 1\nStudent: Answer 1"
        messages = build_critic_messages(
            concept_ground_truth="Ground truth notes",
            student_text="What was the first question?",
            concept_id="oop_lecture_1",
            conversation_history=transcript,
        )
        combined = "\n".join(m["content"] for m in messages)
        assert "### FULL CONVERSATION TRANSCRIPT (TURN-BY-TURN):" in combined
        assert transcript in combined
        assert "Rule 6" in combined

    def test_probe_messages_for_meta_query(self):
        transcript = "Tutor: Initial Q\nStudent: An answer"
        messages = build_probe_messages(
            concept_ground_truth="Ground truth notes",
            student_text="what did you ask?",
            verdict={"verdict": "AMBIGUOUS", "detected_flaw_tag": "STUDENT_META_QUERY"},
            concept_id="oop_lecture_1",
            conversation_history=transcript,
        )
        combined = "\n".join(m["content"] for m in messages)
        assert "STUDENT QUERY ABOUT DIALOGUE / META-QUESTION" in combined
        assert "answer their query directly and accurately" in combined


class TestChatFlowMetaQueryResolution:
    def test_chat_remembers_first_question_when_asked(self, tmp_path):
        """
        Simulate a web chat session where:
        1. Student submits an answer to the opening question.
        2. Student asks 'what was the first question?'.
        3. Agent replies with the exact opening question and prompts them to answer.
        """
        db_path = str(tmp_path / "chat_memory.db")
        store = Store(db_path)
        st = load_settings()

        opening_q = load_opening_question("oop_lecture_1")
        run_id = store.create_run(
            domain="feynman_chat",
            meta={
                "student_id": "2023101001",
                "concept_id": "oop_lecture_1",
                "opening_question": opening_q,
            },
        )
        store.append(run_id, "opening_question", {"text": opening_q}, produced_by="system:opening")

        flow = build_chat_flow(call=StubCompleter())

        # --- Turn 1: Student submits an initial flawed explanation ---
        store.append(run_id, "chat_message", {
            "text": "When I write class Dog, that creates a Dog in memory.",
            "student_id": "2023101001",
        }, produced_by="student:web")

        state1 = runner.advance(store, run_id, flow, st)
        assert state1 == RunState.AWAITING_EXPERT

        probes = store.history(run_id, "probe")
        assert len(probes) == 1
        first_counter_probe = probes[0].payload.get("counter_example_scenario")
        assert first_counter_probe is not None

        # --- Turn 2: Student asks what the first question was ---
        store.append(run_id, "chat_message", {
            "text": "Wait, what was the first question?",
            "student_id": "2023101001",
        }, produced_by="student:web")
        store.set_state(run_id, RunState.DRAFTING)

        state2 = runner.advance(store, run_id, flow, st)
        assert state2 == RunState.AWAITING_EXPERT

        verdicts = store.history(run_id, "verdict")
        assert len(verdicts) == 2
        assert verdicts[1].payload.get("detected_flaw_tag") == "STUDENT_META_QUERY"

        probes = store.history(run_id, "probe")
        assert len(probes) == 2
        second_probe = probes[1].payload.get("counter_example_scenario", "")
        # The agent's response must reference the first question!
        assert "The first question I asked was" in second_probe
        assert opening_q in second_probe
