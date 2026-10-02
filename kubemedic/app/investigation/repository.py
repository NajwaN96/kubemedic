"""SQLite persistence. The repository is the only SQL in the process."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.investigation.models import (
    AIAnalysis,
    EventItem,
    EvidenceItem,
    Investigation,
    LogItem,
    RuleAnalysis,
    TimelineItem,
    TransitionItem,
)


class InvestigationRepository:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS id_counter (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    seq INTEGER NOT NULL UNIQUE,
                    fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    resource_kind TEXT NOT NULL,
                    resource_name TEXT NOT NULL,
                    container TEXT,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detected_issue TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    likely_root_cause TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    events_json TEXT NOT NULL,
                    logs_json TEXT NOT NULL,
                    recommended_actions_json TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL,
                    analysis_source TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_investigations_fingerprint
                    ON investigations (fingerprint, updated_at);
                CREATE TABLE IF NOT EXISTS ai_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    result TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._migrate(connection)

    def _migrate(self, connection: sqlite3.Connection) -> None:
        existing = {row[1] for row in connection.execute("PRAGMA table_info(investigations)")}
        additions = {
            "resolved_at": "TEXT",
            "resolution_reason": "TEXT",
            "recovery_duration_seconds": "INTEGER",
            "last_failure_seen_at": "TEXT",
            "last_healthy_seen_at": "TEXT",
            "stable_restart_count": "INTEGER",
            "timeline_json": "TEXT NOT NULL DEFAULT '[]'",
            "transitions_json": "TEXT NOT NULL DEFAULT '[]'",
            "rule_analysis_json": "TEXT NOT NULL DEFAULT '{}'",
            "ai_analysis_json": "TEXT",
            "ai_status": "TEXT",
            "ai_provider": "TEXT",
            "ai_model": "TEXT",
            "ai_analyzed_at": "TEXT",
            "ai_input_signature": "TEXT",
        }
        for name, declaration in additions.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE investigations ADD COLUMN {name} {declaration}")
        connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def healthy(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def next_id(self) -> tuple[int, str]:
        with self._lock:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT value FROM id_counter WHERE name = 'investigation'"
                ).fetchone()
                value = 1 if row is None else int(row["value"]) + 1
                if row is None:
                    connection.execute(
                        "INSERT INTO id_counter (name, value) VALUES ('investigation', ?)",
                        (value,),
                    )
                else:
                    connection.execute(
                        "UPDATE id_counter SET value = ? WHERE name = 'investigation'",
                        (value,),
                    )
                connection.commit()
        return value, f"INV-{value:06d}"

    def insert(self, investigation: Investigation, seq: int) -> Investigation:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO investigations (
                    id, seq, fingerprint, created_at, updated_at, namespace, resource_kind,
                    resource_name, container, severity, status, detected_issue, summary,
                    likely_root_cause, evidence_json, events_json, logs_json,
                    recommended_actions_json, occurrence_count, analysis_source,
                    resolved_at, resolution_reason, recovery_duration_seconds,
                    last_failure_seen_at, last_healthy_seen_at, stable_restart_count,
                    timeline_json, transitions_json, rule_analysis_json, ai_analysis_json,
                    ai_status, ai_provider, ai_model, ai_analyzed_at, ai_input_signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _row_values(investigation, seq),
            )
            connection.commit()
        return investigation

    def update(self, investigation: Investigation) -> Investigation:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE investigations SET
                    fingerprint = ?, updated_at = ?, namespace = ?, resource_kind = ?,
                    resource_name = ?, container = ?, severity = ?, status = ?,
                    detected_issue = ?, summary = ?, likely_root_cause = ?,
                    evidence_json = ?, events_json = ?, logs_json = ?,
                    recommended_actions_json = ?, occurrence_count = ?, analysis_source = ?,
                    resolved_at = ?, resolution_reason = ?, recovery_duration_seconds = ?,
                    last_failure_seen_at = ?, last_healthy_seen_at = ?, stable_restart_count = ?,
                    timeline_json = ?, transitions_json = ?, rule_analysis_json = ?,
                    ai_analysis_json = ?, ai_status = ?, ai_provider = ?, ai_model = ?,
                    ai_analyzed_at = ?, ai_input_signature = ?
                WHERE id = ?
                """,
                _update_values(investigation),
            )
            connection.commit()
        return investigation

    def get(self, investigation_id: str) -> Investigation | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM investigations WHERE id = ?",
                (investigation_id,),
            ).fetchone()
        return _from_row(row) if row else None

    def list_investigations(
        self,
        status: str | None = None,
        severity: str | None = None,
        issue: str | None = None,
    ) -> list[Investigation]:
        clauses: list[str] = []
        params: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if severity:
            clauses.append("lower(severity) = ?")
            params.append(severity.lower())
        if issue:
            clauses.append("lower(detected_issue) = ?")
            params.append(issue.lower())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM investigations {where} ORDER BY updated_at DESC, seq DESC",
                params,
            ).fetchall()
        return [_from_row(row) for row in rows]

    def find_open(self, fingerprint: str) -> Investigation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM investigations
                WHERE fingerprint = ? AND status IN ('open', 'recovering')
                ORDER BY updated_at DESC LIMIT 1
                """,
                (fingerprint,),
            ).fetchone()
        return _from_row(row) if row else None

    def find_latest(self, fingerprint: str) -> Investigation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM investigations
                WHERE fingerprint = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (fingerprint,),
            ).fetchone()
        return _from_row(row) if row else None

    def find_active(self, namespace: str, kind: str, name: str) -> list[Investigation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM investigations
                WHERE namespace = ? AND resource_kind = ? AND resource_name = ?
                  AND status IN ('open', 'recovering')
                ORDER BY seq ASC
                """,
                (namespace, kind, name),
            ).fetchall()
        return [_from_row(row) for row in rows]

    def list_active(self, namespace: str) -> list[Investigation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM investigations
                WHERE namespace = ? AND status IN ('open', 'recovering')
                ORDER BY seq ASC
                """,
                (namespace,),
            ).fetchall()
        return [_from_row(row) for row in rows]

    def record_ai_call(self, provider: str, result: str, duration_seconds: float) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_calls (provider, result, duration_seconds, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (provider, result, float(duration_seconds), datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()

    def latest_ai_result(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result FROM ai_calls ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return row["result"] if row else None

    def ai_call_counts(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT provider, result, COUNT(*) AS calls
                FROM ai_calls
                GROUP BY provider, result
                """
            ).fetchall()
        return [
            {"provider": row["provider"], "result": row["result"], "calls": int(row["calls"])}
            for row in rows
        ]

    def ai_call_durations(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT provider, duration_seconds FROM ai_calls"
            ).fetchall()
        return [
            {"provider": row["provider"], "seconds": float(row["duration_seconds"])}
            for row in rows
        ]

    def metric_groups(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT severity, detected_issue, analysis_source, status,
                       COUNT(*) AS investigations,
                       COALESCE(SUM(occurrence_count), 0) AS detections
                FROM investigations
                GROUP BY severity, detected_issue, analysis_source, status
                """
            ).fetchall()
        return [
            {
                "severity": row["severity"] or "unknown",
                "issue_type": row["detected_issue"] or "unknown",
                "source": row["analysis_source"] or "rules",
                "status": row["status"],
                "investigations": int(row["investigations"]),
                "detections": int(row["detections"]),
            }
            for row in rows
        ]

    def resolution_durations(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT severity, detected_issue, analysis_source, recovery_duration_seconds
                FROM investigations
                WHERE status = 'resolved' AND recovery_duration_seconds IS NOT NULL
                """
            ).fetchall()
        return [
            {
                "severity": row["severity"] or "unknown",
                "issue_type": row["detected_issue"] or "unknown",
                "source": row["analysis_source"] or "rules",
                "seconds": float(row["recovery_duration_seconds"]),
            }
            for row in rows
        ]


def _dump(value: object) -> str:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    elif isinstance(value, list):
        payload = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
    else:
        payload = value
    return json.dumps(payload)


def _row_values(investigation: Investigation, seq: int) -> tuple:
    return (
        investigation.id,
        seq,
        investigation.fingerprint,
        investigation.created_at.isoformat(),
        investigation.updated_at.isoformat(),
        investigation.namespace,
        investigation.resource_kind,
        investigation.resource_name,
        investigation.container,
        investigation.severity,
        investigation.status,
        investigation.detected_issue,
        investigation.summary,
        investigation.likely_root_cause,
        _dump(investigation.evidence),
        _dump(investigation.events),
        _dump(investigation.logs),
        _dump(investigation.recommended_actions),
        investigation.occurrence_count,
        investigation.analysis_source,
        _iso(investigation.resolved_at),
        investigation.resolution_reason,
        investigation.recovery_duration_seconds,
        _iso(investigation.last_failure_seen_at),
        _iso(investigation.last_healthy_seen_at),
        investigation.stable_restart_count,
        _dump(investigation.timeline),
        _dump(investigation.transitions),
        _dump(investigation.rule_analysis) if investigation.rule_analysis else "{}",
        _dump(investigation.ai_analysis) if investigation.ai_analysis else None,
        investigation.ai_status,
        investigation.ai_provider,
        investigation.ai_model,
        _iso(investigation.ai_analyzed_at),
        investigation.ai_input_signature or None,
    )


def _update_values(investigation: Investigation) -> tuple:
    return (
        investigation.fingerprint,
        investigation.updated_at.isoformat(),
        investigation.namespace,
        investigation.resource_kind,
        investigation.resource_name,
        investigation.container,
        investigation.severity,
        investigation.status,
        investigation.detected_issue,
        investigation.summary,
        investigation.likely_root_cause,
        _dump(investigation.evidence),
        _dump(investigation.events),
        _dump(investigation.logs),
        _dump(investigation.recommended_actions),
        investigation.occurrence_count,
        investigation.analysis_source,
        _iso(investigation.resolved_at),
        investigation.resolution_reason,
        investigation.recovery_duration_seconds,
        _iso(investigation.last_failure_seen_at),
        _iso(investigation.last_healthy_seen_at),
        investigation.stable_restart_count,
        _dump(investigation.timeline),
        _dump(investigation.transitions),
        _dump(investigation.rule_analysis) if investigation.rule_analysis else "{}",
        _dump(investigation.ai_analysis) if investigation.ai_analysis else None,
        investigation.ai_status,
        investigation.ai_provider,
        investigation.ai_model,
        _iso(investigation.ai_analyzed_at),
        investigation.ai_input_signature or None,
        investigation.id,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _from_row(row: sqlite3.Row) -> Investigation:
    return Investigation(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        namespace=row["namespace"],
        resource_kind=row["resource_kind"],
        resource_name=row["resource_name"],
        container=row["container"],
        severity=row["severity"],
        status=row["status"],
        detected_issue=row["detected_issue"],
        summary=row["summary"],
        likely_root_cause=row["likely_root_cause"],
        evidence=[EvidenceItem(**item) for item in json.loads(row["evidence_json"])],
        events=[EventItem(**item) for item in json.loads(row["events_json"])],
        logs=[LogItem(**item) for item in json.loads(row["logs_json"])],
        recommended_actions=json.loads(row["recommended_actions_json"]),
        occurrence_count=row["occurrence_count"],
        analysis_source=row["analysis_source"],
        rule_analysis=_rule_analysis(row["rule_analysis_json"]),
        ai_analysis=_ai_analysis(row["ai_analysis_json"]),
        ai_status=row["ai_status"],
        ai_provider=row["ai_provider"],
        ai_model=row["ai_model"],
        ai_analyzed_at=_parsed(row["ai_analyzed_at"]),
        ai_input_signature=row["ai_input_signature"] or "",
        timeline=[TimelineItem(**item) for item in json.loads(row["timeline_json"] or "[]")],
        transitions=[TransitionItem(**item) for item in json.loads(row["transitions_json"] or "[]")],
        resolved_at=_parsed(row["resolved_at"]),
        resolution_reason=row["resolution_reason"],
        recovery_duration_seconds=row["recovery_duration_seconds"],
        last_failure_seen_at=_parsed(row["last_failure_seen_at"]),
        last_healthy_seen_at=_parsed(row["last_healthy_seen_at"]),
        stable_restart_count=row["stable_restart_count"],
        fingerprint=row["fingerprint"],
    )


def _rule_analysis(raw: str | None) -> RuleAnalysis | None:
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict) or not data.get("detected_issue"):
        return None
    return RuleAnalysis(**data)


def _ai_analysis(raw: str | None) -> AIAnalysis | None:
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict) or not data.get("summary"):
        return None
    return AIAnalysis(**data)


def _parsed(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
