import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.ai.coordinator import AICoordinator
from app.ai.errors import AIDisabledError, AIProviderError
from app.investigation.models import AIAnalysis
from app.investigation.service import InvestigationService
from app.main import create_app
from tests.snapshots import pod_snapshot
from tests.test_api import DisconnectedCluster


def _analysis() -> AIAnalysis:
    return AIAnalysis(
        summary="The process exits before the pod becomes ready.",
        likely_root_cause="Startup is failing with exit code 1.",
        supporting_evidence=["The waiting reason is CrashLoopBackOff."],
        recommended_actions=["Inspect the previous log."],
        contributing_factors=["The container restarts instead of staying up."],
        confidence="medium",
        confidence_explanation="The supplied exit code and waiting reason agree.",
    )


class RecordingAnalyzer:
    provider = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.payloads: list[dict] = []
        self.mode = "ok"
        self.failure = "unavailable"

    def analyze(self, payload: dict) -> AIAnalysis:
        self.payloads.append(payload)
        if self.mode == "ok":
            return _analysis()
        raise AIProviderError(self.failure)


def _enabled(settings, service, analyzer=None):
    enabled = settings.model_copy(update={"ai_enabled": True})
    analyzer = analyzer or RecordingAnalyzer()
    coordinator = AICoordinator(enabled, service.repository, analyzer=analyzer)
    return InvestigationService(service.repository, enabled, ai=coordinator), analyzer


def _crash(name="taskflow-api-abc12", previous="startup failed\n", exit_code=1):
    return pod_snapshot(
        name=name,
        waiting="CrashLoopBackOff",
        terminated_reason="Error",
        exit_code=exit_code,
        restart_count=6,
        previous_log=previous,
        desired=2,
        ready=1,
    )


def test_rules_run_when_ai_is_disabled(service):
    created = service.process_snapshot(_crash())
    assert created.analysis_source == "rules"
    assert created.ai_status is None
    assert created.ai_analysis is None
    assert created.rule_analysis.likely_root_cause == created.likely_root_cause
    assert "startup" in created.likely_root_cause.lower() or "exits" in created.likely_root_cause.lower()


def test_disabled_ai_never_calls_the_provider(settings, service):
    class Boom:
        provider = "fake"
        model = "x"

        def analyze(self, payload):
            raise AssertionError("provider was called")

    settings.ai_enabled = False
    coordinator = AICoordinator(settings, service.repository, analyzer=Boom())
    local = InvestigationService(service.repository, settings, ai=coordinator)
    created = local.process_snapshot(_crash())
    assert created.status == "open"
    assert created.analysis_source == "rules"


def test_ai_augments_rules_without_replacing_them(settings, service):
    local, analyzer = _enabled(settings, service)
    created = local.process_snapshot(
        _crash(previous="password=supersecret\nsk-proj-abcdefghijklmnopqrstuvwxyz\n")
    )
    assert created.status == "open"
    assert created.analysis_source == "rules+ai"
    assert created.ai_status == "ok"
    assert created.ai_analysis.summary == _analysis().summary
    assert created.likely_root_cause != created.ai_analysis.likely_root_cause
    assert created.rule_analysis.likely_root_cause == created.likely_root_cause
    assert created.evidence
    stored = created.model_dump_json()
    assert "supersecret" not in stored
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz" not in stored
    payload = analyzer.payloads[0]
    encoded = str(payload)
    assert "supersecret" not in encoded
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz" not in encoded
    assert "resource_name" not in payload
    assert created.resource_name not in encoded
    assert payload["rule_analysis"]["likely_root_cause"] == created.likely_root_cause

    reloaded = local.get(created.id)
    assert reloaded.ai_analysis.confidence == "medium"
    assert reloaded.analysis_source == "rules+ai"


def test_duplicate_polls_do_not_call_ai_again(settings, service):
    local, analyzer = _enabled(settings, service)
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    snapshot = _crash()
    local.process_snapshot(snapshot, now=start)
    local.process_snapshot(snapshot, now=start + timedelta(seconds=15))
    assert len(analyzer.payloads) == 1
    assert local.get("INV-000001").occurrence_count == 2


def test_material_log_change_allows_another_analysis(settings, service):
    local, analyzer = _enabled(settings, service)
    start = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    local.process_snapshot(_crash(previous="startup failed\n"), now=start)
    local.process_snapshot(_crash(previous="connection refused to database\n", exit_code=2), now=start + timedelta(seconds=20))
    assert len(analyzer.payloads) == 2
    assert local.get("INV-000001").occurrence_count == 2


def test_provider_failure_keeps_the_investigation(settings, service):
    analyzer = RecordingAnalyzer()
    analyzer.mode = "fail"
    analyzer.failure = "quota_exhausted"
    local, _analyzer = _enabled(settings, service, analyzer)
    created = local.process_snapshot(_crash())
    assert created.status == "open"
    assert created.analysis_source == "rules"
    assert created.ai_status == "quota_exhausted"
    assert created.ai_analysis is None
    assert created.likely_root_cause
    assert created.evidence
    assert created.rule_analysis.summary == created.summary


def test_manual_retry_stores_one_analysis(settings, service):
    local, analyzer = _enabled(settings, service)
    created = local.process_snapshot(_crash())
    assert len(analyzer.payloads) == 1
    updated = local.analyze_with_ai(created.id)
    assert len(analyzer.payloads) == 2
    assert updated.ai_status == "ok"
    assert updated.id == created.id
    with pytest.raises(AIDisabledError):
        service.analyze_with_ai(created.id)


def test_missing_key_and_unsupported_provider_do_not_call_openai(settings, service):
    settings.ai_enabled = True
    settings.openai_api_key = ""
    settings.ai_provider = "openai"
    local = InvestigationService(service.repository, settings, ai=AICoordinator(settings, service.repository))
    created = local.process_snapshot(_crash())
    assert created.status == "open"
    assert created.ai_status == "unavailable"
    assert created.analysis_source == "rules"
    assert local.ai.status()["status"] == "unavailable"
    assert "api_key" not in local.ai.status()

    settings.ai_provider = "other"
    local = InvestigationService(service.repository, settings, ai=AICoordinator(settings, service.repository))
    created = local.process_snapshot(_crash(name="taskflow-api-other"))
    assert created.ai_status == "unavailable"
    assert created.analysis_source == "rules"


def test_request_log_records_size_not_secrets(settings, service, caplog):
    local, _analyzer = _enabled(settings, service)
    caplog.set_level(logging.INFO)
    local.process_snapshot(_crash(previous="password=supersecret\nsk-proj-abcdefghijklmnopqrstuvwxyz\n"))
    text = caplog.text
    assert "bytes=" in text
    assert "events=" in text
    assert "log_lines=" in text
    assert "supersecret" not in text
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz" not in text


def test_ai_status_and_metrics_hide_the_key_and_investigation_id(settings):
    settings.ai_enabled = True
    settings.openai_api_key = "sk-test-should-not-leak"
    settings.demo_mode = True
    application = create_app(settings, cluster_connection=DisconnectedCluster(settings))
    application.state.service.ai._analyzer = RecordingAnalyzer()
    with TestClient(application) as client:
        status = client.get("/api/v1/ai/status")
        assert status.status_code == 200
        assert status.json()["enabled"] is True
        assert status.json()["status"] == "configured"
        assert status.json()["model"] == "gpt-test"
        assert "sk-test-should-not-leak" not in status.text

        created = client.post("/api/v1/demo/crashloop")
        assert created.status_code == 200
        assert created.json()["analysis_source"] == "rules+ai"
        connected = client.get("/api/v1/ai/status")
        assert connected.json()["status"] == "connected"

        metrics = client.get("/metrics")
        assert "kubemedic_ai_requests_total" in metrics.text
        assert "kubemedic_ai_success_total" in metrics.text
        assert 'result="success"' in metrics.text
        assert "INV-000001" not in metrics.text
        assert "sk-test-should-not-leak" not in metrics.text

        disabled = client.post("/api/v1/investigations/INV-000009/ai/analyze")
        assert disabled.status_code == 404


def test_manual_endpoint_rejects_a_disabled_provider(settings):
    settings.demo_mode = True
    application = create_app(settings, cluster_connection=DisconnectedCluster(settings))
    with TestClient(application) as client:
        assert client.get("/api/v1/ai/status").json()["status"] == "disabled"
        client.post("/api/v1/demo/oom")
        response = client.post("/api/v1/investigations/INV-000001/ai/analyze")
    assert response.status_code == 409
    assert "disabled" in response.json()["detail"].lower()


def test_ai_package_does_not_mutate_kubernetes():
    from pathlib import Path

    text = "\n".join(path.read_text() for path in Path("app/ai").glob("*.py"))
    for token in ("delete_namespaced", "patch_namespaced", "create_namespaced", "kubernetes.client", "remediation"):
        assert token not in text
