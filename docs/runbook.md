# Lab runbook

Use this when the demo environment misbehaves. It is not a production on-call guide.

## KubeMedic disconnected

`/api/v1/cluster/status` returns `disconnected`, or the dashboard says so.

- `kubectl -n kubemedic get pods` and read the watcher logs.
- Confirm the ServiceAccount `kubemedic` and Role `kubemedic-observer` still exist.
- The dashboard can still serve stored investigations. It cannot see new ones until the watcher connects.
- Restart the deployment only after the logs show a config or RBAC error you have fixed.

## TaskFlow unavailable

The UI on port 41831 fails, or the API readiness is down.

- `kubectl -n taskflow get pods,svc`.
- If the port-forward died, start it again.
- API pods crash-looping: open KubeMedic before you roll back by hand. `make reset` restores the healthy manifests.
- Compose is separate. `make status` checks ports 41821 and 41822.

## PostgreSQL unavailable

`taskflow-postgres-0` is not ready, or the API reports not ready.

- `kubectl -n taskflow get pvc,pod -l app.kubernetes.io/name=taskflow-postgres`
- Scale the StatefulSet back to 1 if a scenario set it to 0.
- Do not delete the PVC unless you intend to drop the tasks.
- `make deploy` will not print or rotate the password when Secret `taskflow-db` already exists.

## Prometheus target down

`kubectl -n monitoring port-forward svc/prometheus 41834:9090`, then open `/targets`.

- TaskFlow and KubeMedic targets depend on the Services and the port name `http`.
- kube-state-metrics has its own Deployment in `monitoring`.
- cAdvisor is scraped through the API server node proxy. The Prometheus ServiceAccount is read-only and is not cluster-admin. If that target is down, the service dashboards still have application metrics.

## Grafana unavailable

Port-forward `svc/grafana` to 41833. Anonymous view is enabled. Login is disabled.

- `kubectl -n monitoring rollout status deployment/grafana`
- Dashboards come from ConfigMap `grafana-dashboards`. `make deploy-monitoring` recreates that ConfigMap from `k8s/monitoring/dashboards/`.

## Investigation stuck open

The workload looks healthy and the incident is still open or recovering.

- Recovery waits `KUBEMEDIC_RECOVERY_STABILIZATION_SECONDS` (default 60). One healthy poll is not enough.
- Stale events older than `KUBEMEDIC_EVENT_FRESHNESS_SECONDS` (default 300) should not hold it open. If a fresh event still describes the failure, the incident stays open.
- Check `resolution_reason` only after it resolves. Evidence remains on the record.

## Remediation failed

The proposal is `failed` or it verified without a generation change. The second case is the REM-000001 lesson. Current code refuses to verify unless generation increases.

- Read `error` and the before/after audit on the investigation.
- Confirm the remediator Pod is the one that executed. A terminating Pod can still accept a request during a rollout.
- A failed proposal is not retried automatically. A verified no-op can be superseded. A verified real change stays.
- Set `KUBEMEDIC_REMEDIATION_ENABLED` back to `false` and restart both KubeMedic deployments when the exercise is over.

## kind cluster unhealthy

- `kubectl get nodes` and `kubectl -n kube-system get pods`.
- If kube-proxy is stuck, `make kind-up` is safe to re-run. It reuses the cluster and switches iptables mode to nftables when needed.
- Do not delete the cluster unless you are willing to lose the SQLite volume and the TaskFlow data. `kind delete cluster --name taskflow` is permanent for this lab.
