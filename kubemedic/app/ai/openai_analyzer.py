"""OpenAI chat provider. The rest of KubeMedic depends on this class only through the coordinator."""

import json

from app.ai.errors import AIProviderError
from app.investigation.models import AIAnalysis

_SYSTEM = """You explain a Kubernetes incident using only the JSON evidence in the user message.
You do not have access to the cluster, to metrics, or to any object that was not included.
Return one JSON object with these keys:
summary, likely_root_cause, supporting_evidence, recommended_actions, contributing_factors, confidence, confidence_explanation.
confidence must be high, medium, or low.
supporting_evidence, recommended_actions, and contributing_factors must be arrays of short strings.
Base every claim on the supplied evidence. If the evidence is thin, say so and use low confidence.
Do not invent resource names, commands, or secret values.
Do not propose patches, shell commands, or direct cluster changes. Recommendations are advisory text.
"""


class OpenAIAnalyzer:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        transient_retries: int = 1,
        client=None,
    ) -> None:
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.transient_retries = max(0, transient_retries)
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    def analyze(self, payload: dict) -> AIAnalysis:
        attempts = self.transient_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    max_tokens=self.max_output_tokens,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": json.dumps(payload, default=str)},
                    ],
                )
                content = ""
                choices = getattr(response, "choices", None) or []
                if choices:
                    content = getattr(choices[0].message, "content", None) or ""
                return parse_ai_content(content)
            except AIProviderError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts and _transient(exc):
                    continue
                raise AIProviderError(classify_provider_error(exc)) from exc
        raise AIProviderError(classify_provider_error(last_error or RuntimeError("unavailable")))


def parse_ai_content(content: str) -> AIAnalysis:
    if not content or not str(content).strip():
        raise AIProviderError("invalid_response")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AIProviderError("invalid_response") from exc
    if not isinstance(data, dict):
        raise AIProviderError("invalid_response")
    try:
        return _validate(data)
    except ValueError as exc:
        raise AIProviderError("invalid_response") from exc


def classify_provider_error(exc: Exception) -> str:
    if isinstance(exc, AIProviderError):
        return exc.status
    name = type(exc).__name__
    text = f"{exc} {getattr(exc, 'body', '')}".lower()
    if (
        "insufficient_quota" in text
        or "insufficient quota" in text
        or "credit_balance_exhausted" in text
        or "credit_balance" in text
    ):
        return "quota_exhausted"
    status_code = getattr(exc, "status_code", None)
    if name == "AuthenticationError" or status_code == 401:
        return "authentication_error"
    if name == "RateLimitError" or status_code == 429:
        return "rate_limited"
    if name == "APITimeoutError" or isinstance(exc, TimeoutError):
        return "timeout"
    if name == "APIConnectionError":
        return "unavailable"
    return "unavailable"


def _transient(exc: Exception) -> bool:
    return type(exc).__name__ in {"APITimeoutError", "APIConnectionError"} or isinstance(exc, TimeoutError)


def _validate(data: dict) -> AIAnalysis:
    confidence = str(data.get("confidence") or "").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        raise ValueError("confidence")
    summary = str(data.get("summary") or "").strip()
    cause = str(data.get("likely_root_cause") or "").strip()
    explanation = str(data.get("confidence_explanation") or "").strip()
    if not summary or not cause or not explanation:
        raise ValueError("text")
    return AIAnalysis(
        summary=summary,
        likely_root_cause=cause,
        supporting_evidence=_strings(data.get("supporting_evidence")),
        recommended_actions=_strings(data.get("recommended_actions")),
        contributing_factors=_strings(data.get("contributing_factors")),
        confidence=confidence,
        confidence_explanation=explanation,
    )


def _strings(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("list")
    return [str(item).strip() for item in value if str(item).strip()]
