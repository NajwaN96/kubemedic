# Failure scenarios

These are lab exercises. Run them against kind, then return TaskFlow to the healthy manifests with `make reset`. Do not commit a change that leaves `KUBEMEDIC_REMEDIATION_ENABLED` true.

KubeMedic deduplicates on namespace, kind, name, issue, and container. Repeating a scenario updates the open investigation.

## CrashLoopBackOff

Simulates a bad rollout whose container exits immediately.

```bash
kubectl -n taskflow patch deployment taskflow-api --type strategic \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","command":["python","-c","raise SystemExit(1)"]}]}}}}'
```

Kubernetes restarts the container. KubeMedic records CrashLoopBackOff, the exit code, and redacted logs. If the Deployment revision is 2 or newer, the proposal is `rollback_deployment`. Otherwise it is `restart_deployment`. Reset with `make reset`.

## Image pull failure

Point the API at an image that does not exist:

```bash
kubectl -n taskflow set image deployment/taskflow-api api=taskflow-api:does-not-exist
```

The Pod stays in ImagePullBackOff or ErrImagePull. Kubernetes retries the pull. KubeMedic keeps the image name and the event. There is no remediation proposal. `make reset` restores `taskflow-api:local`.

## OOMKilled

The API image does not ship a memory bomb. The fixture path is `./scripts/kubemedic-demo.sh oom` against a local demo process, not the cluster. On a cluster, an OOMKilled container is classified high. The recommendation is to inspect memory behavior. KubeMedic will not raise the limit for you.

## CreateContainerConfigError

Scale or edit only if you are willing to restore the Secret. Removing a required key makes the Pod wait on configuration. KubeMedic classifies CreateContainerConfigError and does not propose a Deployment mutation. Restore with `make deploy`, which recreates a missing `taskflow-db` Secret without printing the password. Do not apply `secret.example.yaml`.

## FailedScheduling

Ask for more memory than the node has, on a copy of the workload you can delete:

```bash
kubectl -n taskflow patch deployment taskflow-frontend --type strategic \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"frontend","resources":{"requests":{"memory":"64Gi"}}}]}}}}'
```

The new Pod stays Pending. KubeMedic stores the scheduler message. No remediation. `make reset` restores the requests.

## Readiness and liveness

Probe failures are classified from Pod status and events. Readiness is medium. Liveness is high. Kubernetes stops traffic or restarts the container. KubeMedic does not propose a fix, because the probe or the process has to change. Prefer the fixture `./scripts/kubemedic-demo.sh readiness` if you do not want to edit the live probes.

## Database connectivity

Stop PostgreSQL briefly:

```bash
kubectl -n taskflow scale statefulset taskflow-postgres --replicas=0
```

The API readiness fails. KubeMedic can classify DatabaseConnectivity from redacted logs when the watcher sees them. Bring the database back with `--replicas=1` and wait for the StatefulSet. Do not delete the PVC.

## Unavailable replicas

`kubectl -n taskflow scale deployment taskflow-api --replicas=0` is the case that proposes `scale_deployment` to 1, and only after approval, and only if remediation is enabled. Leave the flag false and the proposal stays a record. Restore with `make reset`.

## Pod deletion

```bash
kubectl -n taskflow delete pod -l app.kubernetes.io/name=taskflow-api --wait=false
```

Kubernetes creates replacements. If the owning Deployment is healthy, KubeMedic does not treat the missing Pod as recovery by itself. A previously open incident resolves only after the stabilization window, with a reason such as `affected Pod was replaced and owning workload is healthy`. Evidence is kept.

## Fixture names

`./scripts/kubemedic-demo.sh` accepts `crashloop`, `bad-image`, `oom`, `missing-secret`, `failed-scheduling`, `readiness`, and `database`. Those replay sanitized snapshots into the local demo database. They do not touch the kind cluster.
