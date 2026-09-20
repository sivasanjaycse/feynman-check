"""
Unit and integration tests for Member 4: Cohort & Escalation Pipeline.
Validates:
- Student session persistence
- Batch telemetry scanning and mathematical aggregation
- Threshold-based escalation trigger (count >= 3)
- Instructor Alert Markdown report formatting
- Human-in-the-Loop review gate ([A]cknowledge / [D]ismiss)
- Flow hook integration (check_and_escalate_batch)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from demo.feynman.batch import (
    BATCH_ALERT_THRESHOLD,
    aggregate_cohort_telemetry,
    check_and_escalate_batch,
    check_escalation_threshold,
    escalate_to_professor,
    generate_instructor_alert,
    get_concept_fallacy_info,
    load_concept_fallacies_from_markdown,
    DEFAULT_FACULTY_EMAIL,
    run_batch_pipeline,
    save_student_session,
    scan_student_records,
    send_email,
)
from demo.feynman.schema import (
    BatchMisconceptionCluster,
    ProfessorEscalationReport,
    StudentSessionRecord,
)
from demo.feynman.stub import CANNED_STUDENTS, get_cohort_records


@pytest.fixture
def temp_workspace(tmp_path: Path):
    """Provides isolated students, telemetry, and reports directories."""
    students_dir = tmp_path / "students"
    students_dir.mkdir(parents=True, exist_ok=True)

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    telemetry_file = tmp_path / "batch_telemetry.json"

    return {
        "students_dir": students_dir,
        "reports_dir": reports_dir,
        "telemetry_file": telemetry_file,
    }


class TestSessionPersistence:
    def test_save_and_scan_student_session(self, temp_workspace):
        students_dir = temp_workspace["students_dir"]
        rec = StudentSessionRecord(
            student_id="20231035053",
            concept_id="virtual_memory",
            iteration_count=1,
            initial_text="TLB miss is a page fault",
            probes_issued=["What happens in RAM first?"],
            student_revisions=["MMU walks the page table in RAM first"],
            final_verdict="MASTERED",
            tagged_fallacy="TLB_MISS_EQUALS_DISK_IO",
        )

        saved_path = save_student_session(rec, student_dir=students_dir)
        assert saved_path.exists()
        assert saved_path.name == "20231035053.json"

        # Verify on-disk JSON
        data = json.loads(saved_path.read_text(encoding="utf-8"))
        assert data["student_id"] == "20231035053"
        assert data["tagged_fallacy"] == "TLB_MISS_EQUALS_DISK_IO"

        # Scan back
        scanned = scan_student_records(student_dir=students_dir)
        assert len(scanned) == 1
        assert scanned[0].student_id == "20231035053"

    def test_scan_empty_directory(self, temp_workspace):
        empty_dir = temp_workspace["students_dir"]
        records = scan_student_records(student_dir=empty_dir)
        assert records == []


class TestCohortTelemetryAggregation:
    def test_aggregate_cohort_telemetry_grouping(self, temp_workspace):
        students_dir = temp_workspace["students_dir"]
        telemetry_file = temp_workspace["telemetry_file"]

        # Commit Dilshan, Siva, and Bakia
        cohort = get_cohort_records()
        for rec in cohort:
            save_student_session(rec, student_dir=students_dir)

        clusters = aggregate_cohort_telemetry(
            student_dir=students_dir, output_file=telemetry_file
        )

        assert "TLB_MISS_EQUALS_DISK_IO" in clusters
        cluster = clusters["TLB_MISS_EQUALS_DISK_IO"]
        assert cluster.occurrence_count == 3
        assert len(cluster.affected_student_ids) == 3
        assert "20231035053" in cluster.affected_student_ids
        assert "20231037154" in cluster.affected_student_ids
        assert "2023103057" in cluster.affected_student_ids
        assert len(cluster.sample_student_quotes) >= 1

        # Check telemetry file on disk
        assert telemetry_file.exists()
        telemetry_json = json.loads(telemetry_file.read_text(encoding="utf-8"))
        assert telemetry_json["total_students_scanned"] == 3
        assert "TLB_MISS_EQUALS_DISK_IO" in telemetry_json["clusters"]

    def test_aggregate_cohort_telemetry_excludes_none_fallacies(self, temp_workspace):
        students_dir = temp_workspace["students_dir"]
        telemetry_file = temp_workspace["telemetry_file"]

        ideal = CANNED_STUDENTS["mastered"]["session_record"]
        save_student_session(ideal, student_dir=students_dir)

        clusters = aggregate_cohort_telemetry(
            student_dir=students_dir, output_file=telemetry_file
        )
        assert len(clusters) == 0


class TestThresholdEvaluation:
    def test_sub_threshold_does_not_breach(self):
        cluster = BatchMisconceptionCluster(
            fallacy_tag="TLB_MISS_EQUALS_DISK_IO",
            occurrence_count=2,  # Below threshold 3
            affected_student_ids=["s1", "s2"],
            sample_student_quotes=["quote"],
            remediation_suggestion="suggestion",
        )
        breached = check_escalation_threshold({"tag": cluster}, threshold=3)
        assert len(breached) == 0

    def test_threshold_breached_at_three(self):
        cluster = BatchMisconceptionCluster(
            fallacy_tag="TLB_MISS_EQUALS_DISK_IO",
            occurrence_count=3,  # Meets threshold 3
            affected_student_ids=["s1", "s2", "s3"],
            sample_student_quotes=["quote"],
            remediation_suggestion="suggestion",
        )
        breached = check_escalation_threshold({"tag": cluster}, threshold=3)
        assert len(breached) == 1
        assert breached[0].fallacy_tag == "TLB_MISS_EQUALS_DISK_IO"


class TestAlertGenerationAndRemediation:
    def test_generate_instructor_alert_report(self, temp_workspace):
        reports_dir = temp_workspace["reports_dir"]
        cluster = BatchMisconceptionCluster(
            fallacy_tag="TLB_MISS_EQUALS_DISK_IO",
            occurrence_count=3,
            affected_student_ids=["20231035053", "20231037154", "2023103057"],
            sample_student_quotes=[
                "TLB miss means data is not in memory",
                "Fetches from hard drive",
            ],
            remediation_suggestion="Draw the 3-Tier Hierarchy on chalkboard: (1) TLB Cache -> (2) RAM Page Table -> (3) Disk Swap.",
        )

        report, report_path = generate_instructor_alert(
            cluster=cluster,
            concept_id="virtual_memory",
            reports_dir=reports_dir,
            date_str="2026-09-19",
        )

        assert report.status == "WAITING_ACK"
        assert report.concept_id == "virtual_memory"
        assert report_path.exists()
        assert report_path.name == "INSTRUCTOR_ALERT_2026-09-19.md"

        content = report_path.read_text(encoding="utf-8")
        assert "URGENT CONCEPT GAP DETECTED" in content
        assert "TLB_MISS_EQUALS_DISK_IO" in content
        assert "3-Tier Hierarchy" in content
        assert "WAITING_FOR_PROFESSOR" in content

        # Generic symlink/file exists too
        assert (reports_dir / "INSTRUCTOR_ALERT.md").exists()


class TestProfessorEscalationGates:
    def test_escalate_to_professor_acknowledge(self):
        report = ProfessorEscalationReport(
            report_id="rep_test_01",
            concept_id="virtual_memory",
            timestamp="2026-09-19T12:00:00Z",
            cluster=BatchMisconceptionCluster(
                fallacy_tag="TLB_MISS_EQUALS_DISK_IO",
                occurrence_count=3,
                affected_student_ids=["s1", "s2", "s3"],
                sample_student_quotes=["q"],
                remediation_suggestion="r",
            ),
            status="WAITING_ACK",
        )

        updated = escalate_to_professor(report, action="A")
        assert updated.status == "ACKNOWLEDGED"

    def test_escalate_to_professor_dismiss(self):
        report = ProfessorEscalationReport(
            report_id="rep_test_02",
            concept_id="virtual_memory",
            timestamp="2026-09-19T12:00:00Z",
            cluster=BatchMisconceptionCluster(
                fallacy_tag="TLB_MISS_EQUALS_DISK_IO",
                occurrence_count=3,
                affected_student_ids=["s1", "s2", "s3"],
                sample_student_quotes=["q"],
                remediation_suggestion="r",
            ),
            status="WAITING_ACK",
        )

        updated = escalate_to_professor(report, action="D")
        assert updated.status == "DISMISSED"

    def test_escalate_to_professor_auto_ack(self):
        report = ProfessorEscalationReport(
            report_id="rep_test_03",
            concept_id="virtual_memory",
            timestamp="2026-09-19T12:00:00Z",
            cluster=BatchMisconceptionCluster(
                fallacy_tag="TLB_MISS_EQUALS_DISK_IO",
                occurrence_count=3,
                affected_student_ids=["s1", "s2", "s3"],
                sample_student_quotes=["q"],
                remediation_suggestion="r",
            ),
            status="WAITING_ACK",
        )

        updated = escalate_to_professor(report, mode="auto_ack")
        assert updated.status == "ACKNOWLEDGED"


class TestPipelineEndToEnd:
    def test_run_batch_pipeline_full_flow(self, temp_workspace):
        students_dir = temp_workspace["students_dir"]
        reports_dir = temp_workspace["reports_dir"]

        # 3 student files with same fallacy
        records = get_cohort_records()
        for r in records:
            save_student_session(r, student_dir=students_dir)

        clusters, reports = run_batch_pipeline(
            student_dir=students_dir,
            reports_dir=reports_dir,
            telemetry_path=temp_workspace["telemetry_file"],
            threshold=3,
            action="A",
        )

        assert len(clusters) == 1
        assert "TLB_MISS_EQUALS_DISK_IO" in clusters
        assert len(reports) == 1
        assert reports[0].status == "ACKNOWLEDGED"
        assert (reports_dir / "INSTRUCTOR_ALERT.md").exists()

    @patch("demo.feynman.batch.send_email")
    def test_check_and_escalate_batch_hook(self, mock_send_email, temp_workspace):
        students_dir = temp_workspace["students_dir"]

        # Commit 3 records
        for r in get_cohort_records():
            save_student_session(r, student_dir=students_dir)

        # Mock context from slice.runner
        mock_ctx = MagicMock()
        mock_ctx.append = MagicMock()

        report = check_and_escalate_batch(
            ctx=mock_ctx,
            student_dir=students_dir,
            reports_dir=temp_workspace["reports_dir"],
            telemetry_path=temp_workspace["telemetry_file"],
            threshold=3,
            interactive=False,
        )

        assert report is not None
        assert report.cluster.fallacy_tag == "TLB_MISS_EQUALS_DISK_IO"
        assert mock_ctx.append.called
        call_args = mock_ctx.append.call_args[0]
        assert call_args[0] == "escalation_report"
        assert mock_send_email.called
        email_kwargs = mock_send_email.call_args.kwargs
        assert "[CONCEPT GAP ALERT]" in email_kwargs.get("subject", "")
        assert "TLB_MISS_EQUALS_DISK_IO" in email_kwargs.get("subject", "")


class TestDynamicConceptSupport:
    def test_load_fallacies_from_deadlocks_markdown(self):
        fallacies = load_concept_fallacies_from_markdown("deadlocks")
        assert "CIRCULAR_WAIT_ALONE_IS_DEADLOCK" in fallacies
        assert "STARVATION_EQUALS_DEADLOCK" in fallacies

        entry = fallacies["CIRCULAR_WAIT_ALONE_IS_DEADLOCK"]
        assert "multiple-instance" in entry["remediation_suggestion"].lower()
        assert "necessary condition" in entry["remediation_suggestion"].lower()

    def test_load_fallacies_from_custom_new_concept_file(self, tmp_path: Path):
        concepts_dir = tmp_path / "concepts"
        concepts_dir.mkdir()

        # Create brand new concept file: scheduling.md
        custom_md = """# Concept Invariants: CPU Scheduling

## 1. Ground Truth Invariants
### Invariant 1: Preemption and Fairness
- Round Robin guarantees time slices.

## 2. Common Fallacy Patterns (Known Misconceptions)

### `QUANTUM_ZERO_ELIMINATES_WAIT`
- **Description:** Student asserts that shrinking the time quantum to zero eliminates thread waiting time without cost.
- **Pedagogical counter:** Shrinking quantum increases context-switch overhead asymptotically towards 100% CPU waste.
"""
        (concepts_dir / "scheduling.md").write_text(custom_md, encoding="utf-8")

        fallacies = load_concept_fallacies_from_markdown("scheduling", concepts_dir=concepts_dir)
        assert "QUANTUM_ZERO_ELIMINATES_WAIT" in fallacies
        info = fallacies["QUANTUM_ZERO_ELIMINATES_WAIT"]
        assert "context-switch overhead" in info["remediation_suggestion"]
        assert "shrinking the time quantum" in info["derailment"].lower()

        # Test get_concept_fallacy_info dynamic fallback
        dynamic_info = get_concept_fallacy_info(
            "QUANTUM_ZERO_ELIMINATES_WAIT", concept_id="scheduling", concepts_dir=concepts_dir
        )
        assert "context-switch overhead" in dynamic_info["remediation_suggestion"]

    def test_generate_alert_with_llm_synthesis(self, temp_workspace):
        reports_dir = temp_workspace["reports_dir"]
        cluster = BatchMisconceptionCluster(
            fallacy_tag="CUSTOM_FALLACY_XYZ",
            occurrence_count=3,
            affected_student_ids=["s1", "s2", "s3"],
            sample_student_quotes=["custom student confusion quote"],
            remediation_suggestion="initial placeholder",
        )

        mock_llm_cluster = BatchMisconceptionCluster(
            fallacy_tag="CUSTOM_FALLACY_XYZ",
            occurrence_count=3,
            affected_student_ids=["s1", "s2", "s3"],
            sample_student_quotes=["custom student confusion quote"],
            remediation_suggestion="Dynamically generated 2-minute lecture intervention by LLM.",
        )
        mock_call_llm = MagicMock(return_value=mock_llm_cluster)

        report, report_path = generate_instructor_alert(
            cluster=cluster,
            concept_id="virtual_memory",
            reports_dir=reports_dir,
            call_llm=mock_call_llm,
        )

        assert mock_call_llm.called
        assert report.cluster.remediation_suggestion == "Dynamically generated 2-minute lecture intervention by LLM."
        report_text = report_path.read_text(encoding="utf-8")
        assert "Dynamically generated 2-minute lecture intervention by LLM." in report_text


class TestRealEmailSender:
    def test_default_faculty_email_address(self):
        assert DEFAULT_FACULTY_EMAIL == "sivasanjayofficial@gmail.com"

    @patch("os.getenv")
    def test_send_email_missing_key(self, mock_getenv):
        def fake_getenv(k, default=""):
            if k == "BREVO_SMTP_KEY":
                return ""
            return default
        mock_getenv.side_effect = fake_getenv

        success = send_email(subject="Test Subject", body="Test Body")
        assert success is False

    @patch("smtplib.SMTP")
    @patch.dict("os.environ", {
        "BREVO_SMTP_KEY": "fake_test_key_12345",
        "BREVO_SMTP_SERVER": "smtp-relay.brevo.com",
        "BREVO_SMTP_PORT": "587",
        "BREVO_SMTP_LOGIN": "ba29a1001@smtp-brevo.com",
        "BREVO_SMTP_FROM": "sivasanjaidisco@gmail.com",
        "FACULTY_EMAIL": "sivasanjayofficial@gmail.com",
    })
    def test_send_email_mocked_smtp_success(self, mock_smtp_cls):
        mock_smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp_instance

        success = send_email(
            subject="Alert: Misconception Found",
            body="Students conflated TLB miss with disk IO",
        )

        assert success is True
        mock_smtp_cls.assert_called_with("smtp-relay.brevo.com", 587, timeout=15)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("ba29a1001@smtp-brevo.com", "fake_test_key_12345")
        assert mock_smtp_instance.send_message.called
        sent_msg = mock_smtp_instance.send_message.call_args[0][0]
        assert sent_msg["Subject"] == "Alert: Misconception Found"
        assert sent_msg["To"] == "sivasanjayofficial@gmail.com"
        assert "sivasanjaidisco@gmail.com" in sent_msg["From"]

    @patch("smtplib.SMTP")
    @patch.dict("os.environ", {
        "BREVO_SMTP_KEY": "fake_test_key_12345",
    })
    def test_send_email_smtp_exception(self, mock_smtp_cls):
        mock_smtp_cls.side_effect = ConnectionRefusedError("Connection refused by SMTP host")

        success = send_email(
            subject="Failing Alert",
            body="Should handle error gracefully",
            recipient="sivasanjayofficial@gmail.com",
        )

        assert success is False


