import json
from types import SimpleNamespace

import pytest

from app.ai.errors import AIProviderError
from app.ai.openai_analyzer import OpenAIAnalyzer, classify_provider_error


class RateLimitError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 429


class AuthenticationError(Exception):
    status_code = 401


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


def _analyzer(script, retries=1):
    class Completions:
        def __init__(self):
            self.calls = []
            self.script = list(script)

        def create(self, **kwargs):
            self.calls.append(kwargs)
            action = self.script.pop(0)
            if isinstance(action, Exception):
                raise action
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=action))])

    completions = Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    analyzer = OpenAIAnalyzer(
        api_key="test-key-should-not-leak",
        model="gpt-test",
        timeout_seconds=5,
        max_output_tokens=80,
        transient_retries=retries,
        client=client,
    )
    return analyzer, completions


def _ok():
    return json.dumps(
        {
            "summary": "The container is exiting during startup.",
            "likely_root_cause": "The process exits before it can serve traffic.",
            "supporting_evidence": ["Exit code 1 is in the supplied evidence."],
            "recommended_actions": ["Read the previous container log."],
            "contributing_factors": ["The restart count is elevated."],
            "confidence": "medium",
            "confidence_explanation": "The exit code and waiting reason agree, and the log is short.",
        }
    )


def test_success_uses_the_configured_model_and_bounds():
    analyzer, completions = _analyzer([_ok()])
    result = analyzer.analyze({"issue": "CrashLoopBackOff"})
    assert result.summary.startswith("The container")
    assert result.confidence == "medium"
    call = completions.calls[0]
    assert call["model"] == "gpt-test"
    assert call["max_tokens"] == 80
    assert call["response_format"] == {"type": "json_object"}
    assert "test-key-should-not-leak" not in json.dumps(call)


def test_quota_429_and_authentication_are_distinct():
    analyzer, completions = _analyzer([RateLimitError("insufficient_quota")], retries=1)
    with pytest.raises(AIProviderError) as quota:
        analyzer.analyze({"issue": "OOMKilled"})
    assert quota.value.status == "quota_exhausted"
    assert len(completions.calls) == 1

    analyzer, completions = _analyzer([RateLimitError("rate limit exceeded")], retries=1)
    with pytest.raises(AIProviderError) as limited:
        analyzer.analyze({"issue": "OOMKilled"})
    assert limited.value.status == "rate_limited"
    assert len(completions.calls) == 1

    analyzer, _completions = _analyzer([AuthenticationError("invalid key")])
    with pytest.raises(AIProviderError) as auth:
        analyzer.analyze({"issue": "OOMKilled"})
    assert auth.value.status == "authentication_error"


def test_timeout_retries_once_and_network_failure_is_unavailable():
    analyzer, completions = _analyzer([APITimeoutError("timed out"), _ok()])
    result = analyzer.analyze({"issue": "CrashLoopBackOff"})
    assert result.confidence == "medium"
    assert len(completions.calls) == 2

    analyzer, completions = _analyzer([APITimeoutError("timed out"), APITimeoutError("timed out")])
    with pytest.raises(AIProviderError) as timed:
        analyzer.analyze({"issue": "CrashLoopBackOff"})
    assert timed.value.status == "timeout"
    assert len(completions.calls) == 2

    analyzer, completions = _analyzer([APIConnectionError("dns failure"), APIConnectionError("dns failure")])
    with pytest.raises(AIProviderError) as network:
        analyzer.analyze({"issue": "CrashLoopBackOff"})
    assert network.value.status == "unavailable"
    assert len(completions.calls) == 2


def test_invalid_empty_and_partial_responses_are_rejected():
    for content in ("", "not-json", "{}", json.dumps({"summary": "only one field"})):
        analyzer, _completions = _analyzer([content])
        with pytest.raises(AIProviderError) as exc:
            analyzer.analyze({"issue": "CrashLoopBackOff"})
        assert exc.value.status == "invalid_response"


def test_classifier_recognizes_credit_exhaustion():
    assert classify_provider_error(RateLimitError("credit_balance_exhausted")) == "quota_exhausted"
