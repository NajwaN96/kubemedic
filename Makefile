.PHONY: help setup local build test logs status demo deploy reset clean clean-k8s kind-up deploy-kubemedic deploy-monitoring kubemedic kubemedic-test kubemedic-status kubemedic-demo validate-k8s terraform-check

help:
	@echo "Local app:        make setup | make test | make local | make status | make logs | make clean"
	@echo "Kind lab:         make kind-up | make deploy | make deploy-kubemedic | make deploy-monitoring | make reset"
	@echo "KubeMedic:        make kubemedic | make kubemedic-test | make kubemedic-status | make kubemedic-demo"
	@echo "Checks:           make validate-k8s | make terraform-check"
	@echo "Cleanup:          make clean | make clean-k8s"

setup:
	./scripts/setup.sh

local: setup
	cd taskflow && docker compose up -d --build

build:
	cd taskflow && docker compose build

test:
	python3 -m venv taskflow/backend/.venv
	. taskflow/backend/.venv/bin/activate && pip install -q -r taskflow/backend/requirements-dev.txt && cd taskflow/backend && pytest

logs:
	@echo "== Docker Compose =="
	@cd taskflow && docker compose logs --tail=100 || true
	@echo
	@echo "== Kubernetes (namespace taskflow) =="
	@if command -v kubectl >/dev/null 2>&1 && kubectl get namespace taskflow >/dev/null 2>&1; then \
		kubectl -n taskflow logs --tail=100 --prefix=true --all-containers=true -l app.kubernetes.io/name=taskflow; \
	else \
		echo "Namespace taskflow is not available on the current cluster."; \
	fi

status:
	cd taskflow && docker compose ps
	@echo
	@curl -fsS http://127.0.0.1:41822/health || echo "API health endpoint is not reachable"
	@echo
	@curl -fsS http://127.0.0.1:41822/ready || echo "API readiness endpoint is not ready"
	@echo
	@echo "== Kubernetes (namespace taskflow) =="
	@if command -v kubectl >/dev/null 2>&1 && kubectl get namespace taskflow >/dev/null 2>&1; then \
		kubectl -n taskflow get pods,deployments,services,statefulsets,pvc; \
	else \
		echo "Namespace taskflow is not available on the current cluster."; \
	fi

demo:
	@echo "TaskFlow local fault injection"
	@echo "--------------------------------"
	@echo "Debug routes stay off unless FAULT_INJECTION_ENABLED=true."
	@echo "They are marked DEMO / TESTING ONLY and are not mounted otherwise."
	@echo
	@echo "  POST /debug/error     return HTTP 500"
	@echo "  POST /debug/slow      delay a response (max 10 seconds)"
	@echo "  POST /debug/memory    allocate at most 64 MB, then release it"
	@echo "  POST /debug/cpu       burn CPU for at most 5 seconds"
	@echo "  POST /debug/crash     terminate the API process"
	@echo
	@echo "On Kubernetes, the only failure exercise in this revision is deleting one API pod."
	@echo "See the Kubernetes section of the README."
	@echo "KubeMedic investigations are replayed with: make kubemedic-demo"

kind-up:
	./scripts/kind-up.sh

deploy:
	./scripts/k8s-deploy.sh

deploy-kubemedic:
	./scripts/k8s-kubemedic.sh

deploy-monitoring:
	./scripts/k8s-monitoring.sh

reset:
	./scripts/k8s-deploy.sh

clean:
	cd taskflow && docker compose down -v --remove-orphans

clean-k8s:
	./scripts/k8s-clean.sh

kubemedic/.venv/bin/uvicorn:
	python3 -m venv kubemedic/.venv
	kubemedic/.venv/bin/pip install -q -r kubemedic/requirements.txt -r kubemedic/requirements-dev.txt

kubemedic-test: kubemedic/.venv/bin/uvicorn
	cd kubemedic && .venv/bin/pytest

kubemedic: kubemedic/.venv/bin/uvicorn
	mkdir -p data
	cd kubemedic && KUBEMEDIC_DB_PATH=$(CURDIR)/data/kubemedic.db KUBEMEDIC_DEMO_MODE=true KUBEMEDIC_WATCH_ENABLED=false .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 41832

kubemedic-status:
	@curl -fsS http://127.0.0.1:41832/health || echo "KubeMedic is not reachable on http://127.0.0.1:41832"
	@echo
	@curl -fsS http://127.0.0.1:41832/api/v1/cluster/status || true
	@echo

kubemedic-demo:
	@./scripts/kubemedic-demo.sh

validate-k8s:
	./scripts/validate-k8s.sh

terraform-check:
	./scripts/terraform-check.sh
