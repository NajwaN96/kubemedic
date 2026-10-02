"""Poll approved remediations and run the typed executor.

Started as `python -m app.remediation.runner`. When remediation is disabled
this process only serves health checks. It never approves its own work.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.config import Settings
from app.investigation.models import TransitionItem
from app.kubernetes.client import ClusterConnection
from app.redact import redact_text
from app.remediation.errors import ExecutionError, PolicyError
from app.remediation.executor import KubernetesDeploymentMutator, recovered
from app.remediation.models import Remediation
from app.remediation.policy import validate_target
from app.remediation.repository import RemediationRepository

logger = logging.getLogger(__name__)


def run_once(repository, settings, mutator, now=None, clock=None, sleep=None) -> int:
    if not settings.remediation_enabled:
        return 0
    moment = now or datetime.now(timezone.utc)
    clock = clock or (lambda: datetime.now(timezone.utc))
    sleep = sleep or time.sleep
    done = 0
    for item in repository.list_remediations(status="approved"):
        claimed = repository.claim(item.id, moment)
        if claimed is None:
            continue
        done += 1
        _finish(claimed, repository, settings, mutator, clock, sleep)
    return done


def _finish(remediation, repository, settings, mutator, clock, sleep) -> None:
    try:
        validate_target(remediation, settings)
        before, after = mutator.apply(remediation, settings)
        if _generation(after) <= _generation(before):
            raise ExecutionError("The Deployment generation did not change.")
    except (PolicyError, ExecutionError, Exception) as exc:
        logger.info("Remediation %s failed before verification", remediation.id)
        _fail(remediation, repository, clock(), exc)
        return
    moment = clock()
    remediation.status = "succeeded"
    remediation.executed_at = moment
    remediation.updated_at = moment
    remediation.before_state = before
    remediation.after_state = after
    remediation.result = "Kubernetes accepted the Deployment patch."
    remediation.transitions.append(
        TransitionItem(at=moment, status="succeeded", reason=remediation.result)
    )
    repository.update(remediation)
    healthy = _verify(remediation, mutator, settings, clock, sleep)
    checked = clock()
    remediation.updated_at = checked
    if healthy is None:
        remediation.status = "failed"
        remediation.error = "The Deployment did not report enough ready replicas before verification timed out."
        remediation.transitions.append(
            TransitionItem(at=checked, status="failed", reason=remediation.error)
        )
    else:
        remediation.status = "verified"
        remediation.verified_at = checked
        remediation.after_state = healthy
        remediation.result = "Deployment ready replicas match the desired count."
        remediation.transitions.append(
            TransitionItem(at=checked, status="verified", reason=remediation.result)
        )
    repository.update(remediation)


def _verify(remediation: Remediation, mutator, settings: Settings, clock, sleep) -> dict | None:
    deadline = clock() + timedelta(seconds=settings.remediation_verify_seconds)
    attempts = max(1, settings.remediation_verify_seconds)
    for _ in range(attempts):
        snapshot = mutator.snapshot(remediation.namespace, remediation.target_name)
        if recovered(snapshot):
            return snapshot
        if clock() >= deadline:
            return None
        remaining = (deadline - clock()).total_seconds()
        sleep(min(2, max(remaining, 0)))
        if clock() >= deadline:
            snapshot = mutator.snapshot(remediation.namespace, remediation.target_name)
            return snapshot if recovered(snapshot) else None
    return None


def _generation(snapshot: dict) -> int:
    value = snapshot.get("generation")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _fail(remediation: Remediation, repository, moment: datetime, exc: Exception) -> None:
    message = redact_text(str(exc) or exc.__class__.__name__)[:300]
    remediation.status = "failed"
    remediation.updated_at = moment
    remediation.error = message or "Remediation failed."
    remediation.transitions.append(TransitionItem(at=moment, status="failed", reason=remediation.error))
    repository.update(remediation)


def _connect_mutator(settings: Settings):
    connection = ClusterConnection(settings).connect()
    if not connection.connected or connection.apps is None:
        logger.warning("Remediator is not connected to Kubernetes. No action will run.")
        return None
    return KubernetesDeploymentMutator(connection.apps)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] in {"/health", "/ready"}:
            body = b'{"status":"ok","service":"kubemedic-remediator"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):
        return


def serve_health(port: int = 8080) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, name="remediator-health", daemon=True)
    thread.start()
    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    serve_health()
    repository = RemediationRepository(settings.db_path)
    mutator = None
    while True:
        if settings.remediation_enabled:
            if mutator is None:
                mutator = _connect_mutator(settings)
            if mutator is not None:
                try:
                    run_once(repository, settings, mutator)
                except Exception:
                    logger.exception("Remediation loop failed")
        time.sleep(max(1, settings.remediation_poll_seconds))


if __name__ == "__main__":
    main()
