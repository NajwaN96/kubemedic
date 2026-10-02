"""Replay a sanitized fixture through the live investigation pipeline.

Usage:
    python -m app.demo crashloop
"""

import json
import sys
from pathlib import Path

from app.config import Settings
from app.investigation.models import Investigation
from app.investigation.repository import InvestigationRepository
from app.investigation.service import InvestigationService

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"

SCENARIOS: dict[str, tuple[str, str]] = {
    "crashloop": ("crashloop.json", "CrashLoopBackOff"),
    "bad-image": ("bad-image.json", "ImagePullBackOff"),
    "oom": ("oom.json", "OOMKilled"),
    "missing-secret": ("missing-secret.json", "CreateContainerConfigError"),
    "failed-scheduling": ("failed-scheduling.json", "FailedScheduling"),
    "readiness": ("readiness.json", "ReadinessProbeFailed"),
    "database": ("database.json", "DatabaseConnectivity"),
}


def scenario_names() -> list[str]:
    return list(SCENARIOS)


def load_scenario(name: str) -> tuple[str, dict]:
    try:
        filename, title = SCENARIOS[name]
    except KeyError as exc:
        known = ", ".join(SCENARIOS)
        raise KeyError(f"Unknown scenario '{name}'. Choose one of: {known}") from exc
    path = FIXTURE_DIR / filename
    return title, json.loads(path.read_text())


def replay(name: str, service: InvestigationService) -> tuple[str, Investigation]:
    title, snapshot = load_scenario(name)
    investigation = service.process_snapshot(snapshot)
    if investigation is None:
        raise RuntimeError(f"Scenario '{name}' did not produce an investigation.")
    return title, investigation


def render(title: str, investigation: Investigation) -> str:
    previous = next((item.content for item in investigation.logs if item.source == "previous"), "")
    current = next((item.content for item in investigation.logs if item.source == "current"), "")
    snippet = _first_line(previous) or _first_line(current)
    exit_code = _evidence_value(investigation, "Exit code")
    restarts = _evidence_value(investigation, "Restart count")
    verb = "created" if investigation.occurrence_count == 1 else "updated"
    lines = [
        f"Replaying scenario: {title}",
        "",
        f"Investigation {verb}:",
        "",
        f"ID: {investigation.id}",
        f"Namespace: {investigation.namespace}",
        f"Resource: {investigation.resource_name}",
        f"Issue: {investigation.detected_issue}",
        f"Severity: {investigation.severity.upper()}",
        "",
        "Likely Root Cause:",
        investigation.likely_root_cause,
        "",
        "Evidence:",
    ]
    if exit_code:
        lines.append(f"Exit code: {exit_code}")
    if restarts:
        lines.append(f"Restart count: {restarts}")
    if snippet:
        lines.append(f"Previous log: {snippet}" if previous else f"Log: {snippet}")
    if not exit_code and not restarts and not snippet:
        for item in investigation.evidence[:4]:
            lines.append(f"{item.label}: {item.value}")
    lines.append("")
    lines.append("Recommended Actions:")
    for index, action in enumerate(investigation.recommended_actions, start=1):
        lines.append(f"{index}. {action}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_help())
        return 0 if args else 2
    settings = Settings()
    service = InvestigationService(InvestigationRepository(settings.db_path), settings)
    try:
        title, investigation = replay(args[0], service)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(render(title, investigation))
    return 0


def _help() -> str:
    names = "\n".join(f"  {name}" for name in SCENARIOS)
    return (
        "Replay a KubeMedic fixture through the investigation pipeline.\n\n"
        "Usage: python -m app.demo <scenario>\n\n"
        f"Scenarios:\n{names}"
    )


def _evidence_value(investigation: Investigation, label: str) -> str:
    for item in investigation.evidence:
        if item.label == label:
            return item.value
    return ""


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
