import os

os.environ.setdefault("KUBEMEDIC_WATCH_ENABLED", "false")
os.environ.setdefault("KUBEMEDIC_DEMO_MODE", "false")

import pytest

from app.config import Settings
from app.investigation.repository import InvestigationRepository
from app.investigation.service import InvestigationService


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        namespace="taskflow",
        incident_cooldown_seconds=300,
        log_tail_lines=100,
        max_log_chars=12000,
        demo_mode=False,
        db_path=str(tmp_path / "kubemedic.db"),
        watch_enabled=False,
        ai_enabled=False,
        openai_api_key="",
        openai_model="gpt-test",
    )


@pytest.fixture
def service(settings) -> InvestigationService:
    return InvestigationService(InvestigationRepository(settings.db_path), settings)
