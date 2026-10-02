"""Prometheus metrics derived from SQLite.

Samples are rebuilt on each scrape from stored investigations, so a process
restart does not zero the counters. Labels stay low-cardinality: severity,
issue type, and analysis source. Resource names, pod UIDs, investigation IDs,
and log text are not labels.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.investigation.repository import InvestigationRepository


def render_metrics(
    repository: InvestigationRepository,
    kubernetes_connected: bool,
    remediations=None,
) -> tuple[bytes, str]:
    registry = CollectorRegistry()
    investigations = Counter(
        "kubemedic_investigations_total",
        "Investigations stored, grouped by severity, issue, and analysis source.",
        ["severity", "issue_type", "source"],
        registry=registry,
    )
    open_investigations = Gauge(
        "kubemedic_open_investigations",
        "Investigations currently open.",
        ["severity", "issue_type", "source"],
        registry=registry,
    )
    recovering = Gauge(
        "kubemedic_recovering_investigations",
        "Investigations whose resource is healthy and still inside the stabilization window.",
        ["severity", "issue_type", "source"],
        registry=registry,
    )
    resolved = Counter(
        "kubemedic_resolved_investigations_total",
        "Investigations that reached resolved.",
        ["severity", "issue_type", "source"],
        registry=registry,
    )
    detections = Counter(
        "kubemedic_detection_total",
        "Failure observations recorded on investigations.",
        ["severity", "issue_type", "source"],
        registry=registry,
    )
    duration = Histogram(
        "kubemedic_investigation_duration_seconds",
        "Seconds from the latest failure observation to resolution.",
        ["severity", "issue_type", "source"],
        buckets=(15, 30, 60, 120, 300, 600, 1800),
        registry=registry,
    )
    connected = Gauge(
        "kubemedic_kubernetes_connected",
        "1 when KubeMedic is connected to the Kubernetes API.",
        registry=registry,
    )
    connected.set(1 if kubernetes_connected else 0)
    ai_requests = Counter(
        "kubemedic_ai_requests_total",
        "AI analysis attempts. Labels are provider and result, never an investigation id.",
        ["provider", "result"],
        registry=registry,
    )
    ai_success = Counter(
        "kubemedic_ai_success_total",
        "AI analysis attempts that returned a valid explanation.",
        ["provider"],
        registry=registry,
    )
    ai_failures = Counter(
        "kubemedic_ai_failures_total",
        "AI analysis attempts that did not return a usable explanation.",
        ["provider", "result"],
        registry=registry,
    )
    ai_duration = Histogram(
        "kubemedic_ai_analysis_duration_seconds",
        "Seconds spent waiting for one AI analysis attempt.",
        ["provider"],
        buckets=(1, 5, 10, 20, 40),
        registry=registry,
    )
    for call in repository.ai_call_counts():
        ai_requests.labels(call["provider"], call["result"]).inc(call["calls"])
        if call["result"] == "success":
            ai_success.labels(call["provider"]).inc(call["calls"])
        else:
            ai_failures.labels(call["provider"], call["result"]).inc(call["calls"])
    for sample in repository.ai_call_durations():
        ai_duration.labels(sample["provider"]).observe(sample["seconds"])

    for row in repository.metric_groups():
        labels = (row["severity"], row["issue_type"], row["source"])
        investigations.labels(*labels).inc(row["investigations"])
        detections.labels(*labels).inc(row["detections"])
        if row["status"] == "open":
            open_investigations.labels(*labels).set(row["investigations"])
        elif row["status"] == "recovering":
            recovering.labels(*labels).set(row["investigations"])
        elif row["status"] == "resolved":
            resolved.labels(*labels).inc(row["investigations"])

    for sample in repository.resolution_durations():
        duration.labels(sample["severity"], sample["issue_type"], sample["source"]).observe(sample["seconds"])

    if remediations is not None:
        remediation_gauge = Gauge(
            "kubemedic_remediations",
            "Stored remediation proposals by allowlisted action and status.",
            ["action", "status"],
            registry=registry,
        )
        for row in remediations.counts():
            remediation_gauge.labels(row["action"], row["status"]).set(row["total"])

    return generate_latest(registry), CONTENT_TYPE_LATEST
