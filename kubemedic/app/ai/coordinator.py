"""Runs at most the AI call the investigation service asks for.

The coordinator records operational counters. It does not log prompt text,
and it does not talk to Kubernetes.
"""

import logging
import time
from dataclasses import dataclass

from app.ai.errors import AIProviderError
from app.ai.openai_analyzer import OpenAIAnalyzer
from app.config import Settings
from app.investigation.models import AIAnalysis
from app.investigation.repository import InvestigationRepository

logger = logging.getLogger(__name__)


@dataclass
class AIOutcome:
    status: str
    analysis: AIAnalysis | None
    provider: str
    model: str


class AICoordinator:
    def __init__(
        self,
        settings: Settings,
        repository: InvestigationRepository,
        analyzer: OpenAIAnalyzer | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self._analyzer = analyzer

    @property
    def enabled(self) -> bool:
        return bool(self.settings.ai_enabled)

    def run(self, payload: dict) -> AIOutcome:
        provider = self.settings.ai_provider or "openai"
        model = self.settings.openai_model
        started = time.perf_counter()
        analysis: AIAnalysis | None = None
        status = "unavailable"
        try:
            analyzer = self._select_analyzer()
            provider = getattr(analyzer, "provider", provider)
            model = getattr(analyzer, "model", model) or model
            analysis = analyzer.analyze(payload)
            status = "ok"
        except AIProviderError as exc:
            status = exc.status
            analysis = None
        except Exception:
            logger.exception("AI analyzer failed before a result was stored")
            status = "unavailable"
            analysis = None
        duration = max(0.0, time.perf_counter() - started)
        metric_result = "success" if status == "ok" else status
        try:
            self.repository.record_ai_call(provider, metric_result, duration)
        except Exception:
            logger.exception("AI call metric was not stored")
        logger.info(
            "AI analysis result provider=%s model=%s result=%s bytes=%s events=%s log_lines=%s",
            provider,
            model,
            metric_result,
            len(str(payload).encode()),
            len(payload.get("recent_events") or []),
            _log_lines(payload),
        )
        return AIOutcome(status=status, analysis=analysis, provider=provider, model=model)

    def status(self) -> dict:
        provider = self.settings.ai_provider or "openai"
        model = self.settings.openai_model
        if not self.enabled:
            state = "disabled"
        elif provider != "openai" and self._analyzer is None:
            state = "unavailable"
        elif self._analyzer is None and not self.settings.openai_api_key:
            state = "unavailable"
        else:
            latest = self.repository.latest_ai_result()
            state = {
                "success": "connected",
                "quota_exhausted": "quota_exhausted",
                "authentication_error": "authentication_error",
            }.get(latest or "", "configured" if latest is None else "unavailable")
        return {
            "enabled": self.enabled,
            "provider": provider,
            "model": model,
            "status": state,
        }

    def _select_analyzer(self):
        if not self.enabled:
            raise AIProviderError("unavailable")
        if self._analyzer is not None:
            return self._analyzer
        provider = self.settings.ai_provider or "openai"
        if provider != "openai":
            raise AIProviderError("unavailable")
        if not self.settings.openai_api_key:
            raise AIProviderError("unavailable")
        return OpenAIAnalyzer(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            timeout_seconds=self.settings.ai_timeout_seconds,
            max_output_tokens=self.settings.ai_max_output_tokens,
            transient_retries=self.settings.ai_transient_retries,
        )


def _log_lines(payload: dict) -> int:
    total = 0
    for item in payload.get("recent_logs") or []:
        total += len(str(item.get("content") or "").splitlines())
    return total
