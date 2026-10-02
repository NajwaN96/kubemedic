# Demo

A 5 to 10 minute walkthrough of the kind lab. No AWS account is required. Do not leave the API crash-looping when you finish.

## Before you start

```bash
make kind-up
make deploy
make deploy-kubemedic
make deploy-monitoring
kubectl -n taskflow port-forward svc/taskflow-frontend 41831:8080
kubectl -n kubemedic port-forward svc/kubemedic 41832:80
kubectl -n monitoring port-forward svc/grafana 41833:3000
```

Confirm the healthy baseline:

```bash
kubectl -n taskflow get pods
curl -fsS http://127.0.0.1:41832/api/v1/cluster/status
curl -fsS http://127.0.0.1:41832/api/v1/remediation/status
```

Expect two API Pods, two frontend Pods, and one PostgreSQL Pod ready. Cluster status is `connected`. Remediation is `enabled: false`. AI is disabled.

Open TaskFlow at http://127.0.0.1:41831 and create one task so the workload is obviously alive.

## Failure

This is the same class of failure as INV-000019. It sets a command that exits immediately, which produces CrashLoopBackOff on a new rollout.

```bash
kubectl -n taskflow patch deployment taskflow-api --type strategic \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","command":["python","-c","import time; raise SystemExit(1)"]}]}}}}'
kubectl -n taskflow get pods -l app.kubernetes.io/name=taskflow-api -w
```

Stop watching when a new Pod shows `CrashLoopBackOff`.

## Investigation

Open http://127.0.0.1:41832. The new investigation should be open, high or critical, issue `CrashLoopBackOff`, analysis `Rules`.

On the detail page, walk through:

- summary and timeline
- evidence, events, and logs
- deterministic analysis
- AI-assisted analysis, which stays disabled
- the remediation proposal, which must not change the Deployment while the flag is false

An approval while disabled returns HTTP 409. That is the point of the gate.

Grafana, dashboard TaskFlow Service Health, should show ready replicas drop. KubeMedic Reliability Overview should show an open investigation.

## Approval

Enable remediation only for this exercise. The Git ConfigMap stays false. This patch is live-cluster state, not a commit.

```bash
kubectl -n kubemedic patch configmap kubemedic-config --type merge \
  -p '{"data":{"KUBEMEDIC_REMEDIATION_ENABLED":"true"}}'
kubectl -n kubemedic rollout restart deployment/kubemedic deployment/kubemedic-remediator
kubectl -n kubemedic rollout status deployment/kubemedic
kubectl -n kubemedic rollout status deployment/kubemedic-remediator
```

Restart the port-forward if it dropped. Approve the rollback in the UI with your name, a reason, and the confirmation checkbox. Or call the API:

```bash
curl -sS -X POST http://127.0.0.1:41832/api/v1/remediations/REM-000000/approve \
  -H 'content-type: application/json' \
  -d '{"approved_by":"operator","reason":"bad command override","confirm":true}'
```

Use the real remediation id from the dashboard. The placeholder above will 404.

Watch the Deployment:

```bash
kubectl -n taskflow get deployment taskflow-api
kubectl -n taskflow get pods -l app.kubernetes.io/name=taskflow-api
```

Success looks like generation advanced, both Pods ready, and the crashing command gone. The remediation status becomes `verified` only after updated ready replicas match the desired count. The investigation moves to recovering, then resolved after the stabilization window (default 60 seconds). One poll does not resolve it.

## Close the lab

Turn remediation off again and restore the healthy manifests if anything is still drifted:

```bash
kubectl -n kubemedic patch configmap kubemedic-config --type merge \
  -p '{"data":{"KUBEMEDIC_REMEDIATION_ENABLED":"false"}}'
kubectl -n kubemedic rollout restart deployment/kubemedic deployment/kubemedic-remediator
make reset
```

`make reset` reapplies TaskFlow. It does not delete KubeMedic's database, so the investigation history remains.

## If you only have a few minutes

Skip the new rollout. Open INV-000019 and REM-000003 on the running cluster and narrate the story in [the README](../README.md#incident-story). Then show Grafana, the CI workflows, and `infra/terraform/README.md`. Say clearly that AWS is not deployed.

## What not to do in a demo

- Do not run `terraform apply` or `terraform plan`.
- Do not enable AI unless you have a key you are willing to use, and do not commit that key.
- Do not apply `k8s/taskflow/backend/secret.example.yaml`.
- Do not grant cluster-admin to the remediator.
