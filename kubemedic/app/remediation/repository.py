"""SQLite storage for remediation proposals and their audit history."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.investigation.models import TransitionItem
from app.remediation.models import Remediation


class RemediationRepository:
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
                CREATE TABLE IF NOT EXISTS remediations (
                    id TEXT PRIMARY KEY,
                    seq INTEGER NOT NULL UNIQUE,
                    investigation_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    replicas INTEGER,
                    approved_by TEXT,
                    approved_at TEXT,
                    approval_reason TEXT,
                    executed_at TEXT,
                    verified_at TEXT,
                    before_state_json TEXT NOT NULL DEFAULT '{}',
                    after_state_json TEXT NOT NULL DEFAULT '{}',
                    result TEXT,
                    error TEXT,
                    transitions_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS idx_remediations_investigation
                    ON remediations (investigation_id, seq);
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def next_id(self) -> tuple[int, str]:
        with self._lock:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT value FROM id_counter WHERE name = 'remediation'"
                ).fetchone()
                value = 1 if row is None else int(row["value"]) + 1
                if row is None:
                    connection.execute(
                        "INSERT INTO id_counter (name, value) VALUES ('remediation', ?)",
                        (value,),
                    )
                else:
                    connection.execute(
                        "UPDATE id_counter SET value = ? WHERE name = 'remediation'",
                        (value,),
                    )
                connection.commit()
        return value, f"REM-{value:06d}"

    def insert(self, remediation: Remediation, seq: int) -> Remediation:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO remediations (
                    id, seq, investigation_id, created_at, updated_at, action, target_kind,
                    target_name, namespace, reason, status, replicas, approved_by, approved_at,
                    approval_reason, executed_at, verified_at, before_state_json, after_state_json,
                    result, error, transitions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _values(remediation, seq),
            )
            connection.commit()
        return remediation

    def update(self, remediation: Remediation) -> Remediation:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE remediations SET
                    updated_at = ?, action = ?, target_kind = ?, target_name = ?, namespace = ?,
                    reason = ?, status = ?, replicas = ?, approved_by = ?, approved_at = ?,
                    approval_reason = ?, executed_at = ?, verified_at = ?, before_state_json = ?,
                    after_state_json = ?, result = ?, error = ?, transitions_json = ?
                WHERE id = ?
                """,
                _update(remediation),
            )
            connection.commit()
        return remediation

    def claim(self, remediation_id: str, moment: datetime) -> Remediation | None:
        with self._lock:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE remediations
                    SET status = 'executing', updated_at = ?
                    WHERE id = ? AND status = 'approved'
                    """,
                    (moment.isoformat(), remediation_id),
                )
                connection.commit()
                if cursor.rowcount != 1:
                    return None
        current = self.get(remediation_id)
        if current is None:
            return None
        current.transitions.append(TransitionItem(at=moment, status="executing", reason="Approved action started"))
        return self.update(current)

    def get(self, remediation_id: str) -> Remediation | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM remediations WHERE id = ?",
                (remediation_id,),
            ).fetchone()
        return _from_row(row) if row else None

    def list_for_investigation(self, investigation_id: str) -> list[Remediation]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM remediations
                WHERE investigation_id = ?
                ORDER BY seq ASC
                """,
                (investigation_id,),
            ).fetchall()
        return [_from_row(row) for row in rows]

    def list_remediations(self, status: str | None = None) -> list[Remediation]:
        if status:
            query = "SELECT * FROM remediations WHERE status = ? ORDER BY seq DESC"
            params: tuple = (status,)
        else:
            query = "SELECT * FROM remediations ORDER BY seq DESC"
            params = ()
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_from_row(row) for row in rows]

    def latest_for(self, investigation_id: str, action: str, target_name: str) -> Remediation | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM remediations
                WHERE investigation_id = ? AND action = ? AND target_name = ?
                ORDER BY seq DESC LIMIT 1
                """,
                (investigation_id, action, target_name),
            ).fetchone()
        return _from_row(row) if row else None

    def counts(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT action, status, COUNT(*) AS total
                FROM remediations
                GROUP BY action, status
                """
            ).fetchall()
        return [
            {"action": row["action"], "status": row["status"], "total": int(row["total"])}
            for row in rows
        ]


def _values(remediation: Remediation, seq: int) -> tuple:
    return (
        remediation.id,
        seq,
        remediation.investigation_id,
        remediation.created_at.isoformat(),
        remediation.updated_at.isoformat(),
        remediation.action,
        remediation.target_kind,
        remediation.target_name,
        remediation.namespace,
        remediation.reason,
        remediation.status,
        remediation.replicas,
        remediation.approved_by,
        _iso(remediation.approved_at),
        remediation.approval_reason,
        _iso(remediation.executed_at),
        _iso(remediation.verified_at),
        json.dumps(remediation.before_state),
        json.dumps(remediation.after_state),
        remediation.result,
        remediation.error,
        json.dumps([item.model_dump(mode="json") for item in remediation.transitions]),
    )


def _update(remediation: Remediation) -> tuple:
    return (
        remediation.updated_at.isoformat(),
        remediation.action,
        remediation.target_kind,
        remediation.target_name,
        remediation.namespace,
        remediation.reason,
        remediation.status,
        remediation.replicas,
        remediation.approved_by,
        _iso(remediation.approved_at),
        remediation.approval_reason,
        _iso(remediation.executed_at),
        _iso(remediation.verified_at),
        json.dumps(remediation.before_state),
        json.dumps(remediation.after_state),
        remediation.result,
        remediation.error,
        json.dumps([item.model_dump(mode="json") for item in remediation.transitions]),
        remediation.id,
    )


def _from_row(row: sqlite3.Row) -> Remediation:
    return Remediation(
        id=row["id"],
        investigation_id=row["investigation_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        action=row["action"],
        target_kind=row["target_kind"],
        target_name=row["target_name"],
        namespace=row["namespace"],
        reason=row["reason"],
        status=row["status"],
        replicas=row["replicas"],
        approved_by=row["approved_by"],
        approved_at=_parsed(row["approved_at"]),
        approval_reason=row["approval_reason"],
        executed_at=_parsed(row["executed_at"]),
        verified_at=_parsed(row["verified_at"]),
        before_state=json.loads(row["before_state_json"] or "{}"),
        after_state=json.loads(row["after_state_json"] or "{}"),
        result=row["result"],
        error=row["error"],
        transitions=[TransitionItem(**item) for item in json.loads(row["transitions_json"] or "[]")],
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parsed(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
