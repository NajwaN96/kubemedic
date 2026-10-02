"""Deterministic investigation rules.

Severity, highest matching condition wins inside each issue:

- critical: a workload wants replicas and none are ready
- high: CrashLoopBackOff, OOMKilled, image pull failure,
  container config failure, liveness failure, database connectivity failure
- medium: readiness failure, scheduling failure, mount failure,
  degraded replicas, repeated restarts
- low: anything else that still produced an investigation

Rules never change Kubernetes objects. This module does not call an AI provider.
"""

from dataclasses import dataclass, field

HIGH_ISSUES = {
    "CrashLoopBackOff",
    "OOMKilled",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "CreateContainerError",
    "LivenessProbeFailed",
    "DatabaseConnectivity",
}
MEDIUM_ISSUES = {
    "ReadinessProbeFailed",
    "FailedScheduling",
    "FailedMount",
    "UnavailableReplicas",
    "RepeatedRestarts",
}


@dataclass
class Finding:
    detected_issue: str
    summary: str
    likely_root_cause: str
    recommended_actions: list[str] = field(default_factory=list)
    severity: str = "medium"


def severity_for(issue: str, desired: int | None, ready: int | None) -> str:
    outage = desired is not None and desired > 0 and (ready or 0) == 0
    if outage and issue in HIGH_ISSUES | MEDIUM_ISSUES | {"UnavailableReplicas"}:
        return "critical"
    if issue in HIGH_ISSUES:
        return "high"
    if issue in MEDIUM_ISSUES:
        return "medium"
    return "low"


def analyze(evidence: dict) -> Finding:
    issue = evidence["detected_issue"]
    desired = evidence.get("deployment_desired")
    ready = evidence.get("deployment_ready")
    messages = _messages(evidence)
    logs = f"{evidence.get('previous_logs') or ''}\n{evidence.get('logs') or ''}"
    database_failure = _database_signals(logs)
    rule = _RULES.get(issue, _generic)
    finding = rule(evidence, messages, database_failure)
    finding.severity = severity_for(issue, desired, ready)
    return finding


def _messages(evidence: dict) -> str:
    parts = [evidence.get("waiting_message") or "", evidence.get("event_text") or ""]
    return "\n".join(part for part in parts if part)


def _database_signals(logs: str) -> bool:
    text = logs.lower()
    if not text.strip():
        return False
    mentions_database = any(
        token in text
        for token in ("postgres", "database", "psycopg", "sqlalchemy", "taskflow-postgres")
    )
    failed = any(
        token in text
        for token in (
            "connection refused",
            "could not connect",
            "connection timeout",
            "operationalerror",
            "database unavailable",
            "password authentication failed",
        )
    )
    return mentions_database and failed


def _crashloop(evidence: dict, messages: str, database_failure: bool) -> Finding:
    if evidence.get("container") == "api":
        cause = "The API container repeatedly exits during startup."
    else:
        cause = "The container repeatedly starts and exits."
    actions = [
        "Inspect previous container logs.",
        "Verify environment configuration.",
        "Verify application startup dependencies.",
    ]
    if database_failure:
        actions = [
            "Verify PostgreSQL availability.",
            "Verify the database hostname.",
            *actions,
        ]
    return Finding(
        detected_issue="CrashLoopBackOff",
        summary="The container is in CrashLoopBackOff and exits during startup.",
        likely_root_cause=cause,
        recommended_actions=actions,
    )


def _image_pull(evidence: dict, messages: str, database_failure: bool) -> Finding:
    category = _image_category(messages)
    if category == "registry authentication":
        cause = "The kubelet could not authenticate to the image registry."
        actions = [
            "Confirm the image pull Secret exists in this namespace and is referenced by the Pod.",
            "Confirm the registry credentials are valid.",
            "Do not copy registry tokens into the investigation output.",
        ]
    elif category == "invalid image or tag":
        cause = "The image name or tag does not exist in the registry."
        actions = [
            "Check the image repository and tag on the container.",
            "Confirm that tag was built and pushed to the registry the cluster uses.",
            "For a local cluster, load taskflow-api:local or taskflow-frontend:local into the node.",
        ]
    elif category == "registry unavailable":
        cause = "The kubelet could not reach the image registry."
        actions = [
            "Check registry DNS and network access from the node.",
            "Retry after the registry is reachable.",
            "Confirm the image reference is not pointing at the wrong registry host.",
        ]
    else:
        cause = "The kubelet could not pull the container image."
        actions = [
            "Read the image pull event message.",
            "Check the image name, tag, registry reachability, and pull credentials.",
        ]
    image = evidence.get("image") or "the configured image"
    return Finding(
        detected_issue=evidence["detected_issue"],
        summary=f"The container cannot start because pulling {image} failed ({category}).",
        likely_root_cause=cause,
        recommended_actions=actions,
    )


def _image_category(messages: str) -> str:
    text = messages.lower()
    if any(token in text for token in ("unauthorized", "authentication required", "denied", "401")):
        return "registry authentication"
    # containerd wraps several failures in "failed to resolve reference".
    # DNS and dial errors have to win over that wrapper.
    if any(token in text for token in ("timeout", "connection refused", "dial tcp", "i/o timeout", "no such host")):
        return "registry unavailable"
    if any(token in text for token in ("manifest unknown", "not found", "404", "failed to resolve reference")):
        return "invalid image or tag"
    return "image pull failed"


def _oom(evidence: dict, messages: str, database_failure: bool) -> Finding:
    limit = evidence.get("memory_limit")
    limit_text = f" The container memory limit is {limit}." if limit else ""
    return Finding(
        detected_issue="OOMKilled",
        summary="The container was OOMKilled.",
        likely_root_cause=(
            "The container exceeded its allowed memory and the kernel killed it." + limit_text
        ),
        recommended_actions=[
            "Inspect recent memory usage and compare it with the container limit.",
            "Review the application for unbounded caches, large allocations, or leaks.",
            "Review CPU and memory requests together with the limit and the workload's real usage.",
            "Change the limit only after the memory behavior is understood. Raising it is not the whole fix.",
        ],
    )


def _config_error(evidence: dict, messages: str, database_failure: bool) -> Finding:
    text = messages.lower()
    if "secret" in text and "not found" in text:
        cause = "The Pod references a Secret that is missing or not visible in the namespace."
        actions = [
            "Read the event to identify the Secret name.",
            "Create that Secret in the namespace without committing the value to Git.",
            "Confirm the env or volume reference uses the same name and key.",
        ]
    elif "configmap" in text and "not found" in text:
        cause = "The Pod references a ConfigMap that is missing."
        actions = [
            "Read the event to identify the ConfigMap name.",
            "Apply the missing ConfigMap or fix the reference.",
            "Confirm the key named in the Pod exists in the ConfigMap.",
        ]
    else:
        cause = "Kubernetes could not build the container configuration from the Pod spec."
        actions = [
            "Read the CreateContainerConfigError event message.",
            "Check Secret, ConfigMap, and environment references on the Pod.",
            "Do not copy Secret values into notes or chat.",
        ]
    return Finding(
        detected_issue=evidence["detected_issue"],
        summary="Kubernetes could not create the container because its configuration is invalid.",
        likely_root_cause=cause,
        recommended_actions=actions,
    )


def _failed_mount(evidence: dict, messages: str, database_failure: bool) -> Finding:
    text = messages.lower()
    if "persistentvolumeclaim" in text or "pvc" in text or "unbound" in text:
        cause = "A volume mount is waiting on a PersistentVolumeClaim."
        actions = [
            "Check that the PersistentVolumeClaim exists and is Bound.",
            "Confirm the Pod is scheduled to a node that can attach the volume.",
            "Read the FailedMount event for the claim name.",
        ]
    elif "secret" in text:
        cause = "A volume mount references a Secret that is missing or unreadable."
        actions = [
            "Identify the Secret name from the event.",
            "Create the Secret in the namespace without storing its value in Git.",
        ]
    elif "configmap" in text:
        cause = "A volume mount references a ConfigMap that is missing."
        actions = [
            "Identify the ConfigMap name from the event.",
            "Apply the ConfigMap or correct the volume reference.",
        ]
    else:
        cause = "Kubernetes could not mount a volume required by the Pod."
        actions = [
            "Read the FailedMount event.",
            "Check PersistentVolumeClaim, Secret, and ConfigMap references.",
        ]
    return Finding(
        detected_issue="FailedMount",
        summary="A volume required by the Pod is not mounting.",
        likely_root_cause=cause,
        recommended_actions=actions,
    )


def _failed_scheduling(evidence: dict, messages: str, database_failure: bool) -> Finding:
    text = messages.lower()
    if "insufficient cpu" in text:
        cause = "The scheduler did not place the Pod because CPU requests do not fit the nodes."
    elif "insufficient memory" in text:
        cause = "The scheduler did not place the Pod because memory requests do not fit the nodes."
    elif "untolerated taint" in text or "taint" in text:
        cause = "The scheduler rejected the nodes because of taints the Pod does not tolerate."
    elif "node selector" in text or "node affinity" in text or "didn't match" in text:
        cause = "The Pod node selector or affinity did not match any node."
    elif "persistentvolumeclaim" in text or "unbound immediate" in text:
        cause = "The scheduler is waiting on a PersistentVolumeClaim constraint."
    else:
        cause = "The scheduler could not bind the Pod to a node."
    return Finding(
        detected_issue="FailedScheduling",
        summary="The Pod is Pending because it cannot be scheduled.",
        likely_root_cause=cause,
        recommended_actions=[
            "Read the scheduler event message before changing requests.",
            "Compare the Pod requests with node allocatable CPU and memory.",
            "Check taints, tolerations, node selectors, and unbound PersistentVolumeClaims.",
        ],
    )


def _readiness(evidence: dict, messages: str, database_failure: bool) -> Finding:
    actions = [
        "Read the probe path and port from the event.",
        "Check whether the process is listening and the dependency it calls is reachable.",
        "A failing readiness probe removes the Pod from Service endpoints. Kubernetes will not replace it for readiness alone.",
    ]
    cause = "The readiness probe failed, so the Pod is not receiving Service traffic."
    if database_failure:
        cause = "The readiness probe failed. Logs show the process cannot reach PostgreSQL."
        actions.insert(0, "Verify PostgreSQL connectivity from the API without printing credentials.")
    return Finding(
        detected_issue="ReadinessProbeFailed",
        summary="The readiness probe is failing.",
        likely_root_cause=cause,
        recommended_actions=actions,
    )


def _liveness(evidence: dict, messages: str, database_failure: bool) -> Finding:
    return Finding(
        detected_issue="LivenessProbeFailed",
        summary="The liveness probe is failing and Kubernetes is restarting the container.",
        likely_root_cause="The liveness probe did not succeed, so the kubelet restarts the container.",
        recommended_actions=[
            "Read the probe path, port, and failure message in the event.",
            "Check whether the process is deadlocked or blocked on a dependency.",
            "Inspect the previous container logs after the restart.",
        ],
    )


def _database(evidence: dict, messages: str, database_failure: bool) -> Finding:
    return Finding(
        detected_issue="DatabaseConnectivity",
        summary="Dependency failure: the application cannot reach PostgreSQL.",
        likely_root_cause="Application logs show a database connection failure. Credentials were not collected.",
        recommended_actions=[
            "Verify the PostgreSQL Service and Pod are ready.",
            "Verify DATABASE_HOST and DATABASE_PORT point at taskflow-postgres:5432.",
            "Confirm the database Secret exists. Do not print the password.",
            "Inspect application logs after redaction.",
        ],
    )


def _restarts(evidence: dict, messages: str, database_failure: bool) -> Finding:
    count = evidence.get("restart_count")
    return Finding(
        detected_issue="RepeatedRestarts",
        summary=f"The container has restarted {count} times.",
        likely_root_cause="The container is restarting repeatedly without a more specific waiting reason.",
        recommended_actions=[
            "Inspect current and previous container logs.",
            "Check the last termination reason and exit code.",
        ],
    )


def _unavailable(evidence: dict, messages: str, database_failure: bool) -> Finding:
    ready = evidence.get("deployment_ready")
    desired = evidence.get("deployment_desired")
    return Finding(
        detected_issue="UnavailableReplicas",
        summary="The Deployment has fewer ready replicas than desired.",
        likely_root_cause=f"Ready replicas are {ready} of {desired}.",
        recommended_actions=[
            "List Pods for the Deployment and read their container status.",
            "Read namespace Events for the failing Pods.",
        ],
    )


def _generic(evidence: dict, messages: str, database_failure: bool) -> Finding:
    issue = evidence["detected_issue"]
    return Finding(
        detected_issue=issue,
        summary=f"KubeMedic detected {issue}.",
        likely_root_cause="The collected Pod status and events match this condition.",
        recommended_actions=["Inspect the Pod status, Events, and recent logs."],
    )


_RULES = {
    "CrashLoopBackOff": _crashloop,
    "ImagePullBackOff": _image_pull,
    "ErrImagePull": _image_pull,
    "OOMKilled": _oom,
    "CreateContainerConfigError": _config_error,
    "CreateContainerError": _config_error,
    "FailedMount": _failed_mount,
    "FailedScheduling": _failed_scheduling,
    "ReadinessProbeFailed": _readiness,
    "LivenessProbeFailed": _liveness,
    "DatabaseConnectivity": _database,
    "RepeatedRestarts": _restarts,
    "UnavailableReplicas": _unavailable,
}
