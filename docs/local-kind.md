# Local kind lab

The runtime for this project is a kind cluster named `taskflow`. Docker Compose is the single-machine path for TaskFlow alone.

## Prerequisites

- Docker Engine and Compose v2
- Python 3.11 or newer
- kind and kubectl for the cluster path
- Node 22 only if you build the frontend on the host

`make kind-up` sets `KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER=native` when it creates the cluster. On this kernel it also switches kube-proxy from iptables to nftables when the ConfigMap still says iptables.

## Create and deploy

```bash
make setup
make kind-up
make deploy
make deploy-kubemedic
make deploy-monitoring
```

`make deploy` builds nothing by itself. It expects local images `taskflow-api:local` and `taskflow-frontend:local`, loads them into kind, and creates Secret `taskflow-db` when that Secret is missing. The password is not printed and is not written to Git.

`make deploy-kubemedic` applies the watcher, the remediator, the PVC, and the ConfigMap. Remediation and AI stay false.

## Ports

| Service | Command | URL |
| --- | --- | --- |
| TaskFlow UI | `kubectl -n taskflow port-forward svc/taskflow-frontend 41831:8080` | http://127.0.0.1:41831 |
| KubeMedic | `kubectl -n kubemedic port-forward svc/kubemedic 41832:80` | http://127.0.0.1:41832 |
| Grafana | `kubectl -n monitoring port-forward svc/grafana 41833:3000` | http://127.0.0.1:41833 |
| Prometheus | `kubectl -n monitoring port-forward svc/prometheus 41834:9090` | http://127.0.0.1:41834 |

Compose uses 41821, 41822, and 41823 on `127.0.0.1` and does not need these forwards.

A rollout closes the KubeMedic port-forward. Start it again after a restart.

## Status

```bash
kubectl get pods -A
curl -fsS http://127.0.0.1:41832/api/v1/cluster/status
curl -fsS http://127.0.0.1:41832/api/v1/remediation/status
curl -fsS http://127.0.0.1:41832/api/v1/ai/status
```

Healthy means API `2/2`, frontend `2/2`, PostgreSQL `1/1`, KubeMedic and the remediator `1/1`, Prometheus ready, and Grafana HTTP 200.

## Images

Kind does not see the host Docker images until they are imported. `make deploy` does that for TaskFlow. For a rebuilt KubeMedic image the node uses the native snapshotter:

```bash
docker build -t kubemedic:local kubemedic
docker save kubemedic:local | docker exec -i taskflow-control-plane ctr -n k8s.io images import --snapshotter native --local -
kubectl -n kubemedic rollout restart deployment/kubemedic deployment/kubemedic-remediator
```

Manifests stay on the tag `:local`. CI archives are tagged `sha-<12>` and are not what the cluster runs.

## Failure exercises and cleanup

See [failure-scenarios.md](failure-scenarios.md) and [demo.md](demo.md).

```bash
make reset
```

restores TaskFlow manifests. It does not wipe KubeMedic's SQLite volume.

```bash
make clean-k8s
```

deletes namespace `taskflow` only. KubeMedic and monitoring stay.

```bash
make clean
```

stops Compose and deletes its database volume.

## Fixture path

`make kubemedic` starts the API on port 41832 with demo mode on and the watcher off. `./scripts/kubemedic-demo.sh crashloop` replays a sanitized fixture into `data/kubemedic.db`. That database is gitignored. It is not the cluster database.
