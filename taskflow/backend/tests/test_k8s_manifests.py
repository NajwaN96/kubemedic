"""Static checks for the TaskFlow Kubernetes manifests.

These tests do not require a cluster. They keep passwords out of Git and
keep the Docker Compose frontend proxy pointed at the Compose service.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_ROOT = ROOT / "k8s" / "taskflow"


def documents():
    found = []
    for path in sorted(MANIFEST_ROOT.rglob("*.yaml")):
        text = path.read_text()
        for document in yaml.safe_load_all(text):
            if document:
                found.append((path, document))
    return found


def by_kind(kind: str):
    return [doc for _, doc in documents() if doc.get("kind") == kind]


def one(kind: str, name: str):
    matches = [doc for doc in by_kind(kind) if doc["metadata"]["name"] == name]
    assert len(matches) == 1, f"expected one {kind}/{name}"
    return matches[0]


def test_every_namespaced_object_is_in_taskflow():
    for path, doc in documents():
        if doc["kind"] == "Namespace":
            assert doc["metadata"]["name"] == "taskflow"
            continue
        assert doc["metadata"].get("namespace") == "taskflow", path


def test_workloads_and_services_exist():
    frontend = one("Deployment", "taskflow-frontend")
    api = one("Deployment", "taskflow-api")
    database = one("StatefulSet", "taskflow-postgres")
    assert frontend["spec"]["replicas"] == 2
    assert api["spec"]["replicas"] == 2
    assert database["spec"]["replicas"] == 1
    assert database["spec"]["serviceName"] == "taskflow-postgres"
    assert one("Service", "taskflow-frontend")["spec"]["type"] == "ClusterIP"
    assert one("Service", "taskflow-api")["spec"]["ports"][0]["port"] == 8000
    assert one("Service", "taskflow-postgres")["spec"]["clusterIP"] == "None"
    assert one("PersistentVolumeClaim", "taskflow-postgres-data")["spec"]["resources"]["requests"]["storage"] == "1Gi"


def test_backend_uses_existing_probes_and_local_image():
    api = one("Deployment", "taskflow-api")
    container = api["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "taskflow-api:local"
    assert container["imagePullPolicy"] == "IfNotPresent"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/ready"
    assert container["livenessProbe"]["periodSeconds"] >= 10
    assert container["readinessProbe"]["timeoutSeconds"] >= 5
    assert container["resources"]["requests"]["memory"]
    assert container["resources"]["limits"]["memory"]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert "ALL" in container["securityContext"]["capabilities"]["drop"]


def test_frontend_image_and_nginx_override():
    frontend = one("Deployment", "taskflow-frontend")
    container = frontend["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "taskflow-frontend:local"
    assert container["imagePullPolicy"] == "IfNotPresent"
    assert container["livenessProbe"]["httpGet"]["path"] == "/"
    assert container["readinessProbe"]["httpGet"]["path"] == "/"
    mounts = {item["mountPath"] for item in container["volumeMounts"]}
    assert "/etc/nginx/conf.d/default.conf" in mounts
    config = one("ConfigMap", "taskflow-frontend-nginx")["data"]["default.conf"]
    assert "taskflow-api.taskflow.svc.cluster.local:8000" in config
    assert "kube-dns.kube-system.svc.cluster.local" in config


def test_config_and_secret_split():
    config = one("ConfigMap", "taskflow-api-config")["data"]
    assert config["DATABASE_HOST"] == "taskflow-postgres"
    assert config["DATABASE_PORT"] == "5432"
    assert config["DATABASE_NAME"] == "taskflow"
    assert config["DATABASE_USER"] == "taskflow"
    assert config["FAULT_INJECTION_ENABLED"] == "false"
    assert "PASSWORD" not in "".join(config)

    example = one("Secret", "taskflow-db")
    assert example["stringData"]["password"] == "CHANGE_ME"
    applied_secrets = [
        doc
        for path, doc in documents()
        if doc.get("kind") == "Secret" and path.name != "secret.example.yaml"
    ]
    assert applied_secrets == []


def test_workloads_read_the_password_from_the_secret():
    for kind, name in (("Deployment", "taskflow-api"), ("StatefulSet", "taskflow-postgres")):
        workload = one(kind, name)
        containers = workload["spec"]["template"]["spec"]["containers"]
        rendered = yaml.safe_dump(containers)
        assert "secretKeyRef" in rendered
        assert "taskflow-db" in rendered
        assert "CHANGE_ME" not in rendered
        assert "POSTGRES_PASSWORD=" not in rendered
        assert "DATABASE_PASSWORD=" not in rendered


def test_ingress_routes_frontend_and_api_separately():
    frontend = one("Ingress", "taskflow-frontend")
    api = one("Ingress", "taskflow-api")
    frontend_path = frontend["spec"]["rules"][0]["http"]["paths"][0]
    api_path = api["spec"]["rules"][0]["http"]["paths"][0]
    assert frontend_path["path"] == "/"
    assert frontend_path["backend"]["service"]["name"] == "taskflow-frontend"
    assert api_path["path"] == "/api(/|$)(.*)"
    assert api_path["backend"]["service"]["name"] == "taskflow-api"
    assert api["metadata"]["annotations"]["nginx.ingress.kubernetes.io/rewrite-target"] == "/$2"


def test_postgres_is_a_single_replica_demo():
    database = one("StatefulSet", "taskflow-postgres")
    container = database["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "postgres:16-alpine"
    assert container["securityContext"]["runAsUser"] == 70
    assert container["securityContext"]["runAsNonRoot"] is True
    assert container["resources"]["limits"]["memory"]
    claim = database["spec"]["template"]["spec"]["volumes"][0]["persistentVolumeClaim"]["claimName"]
    assert claim == "taskflow-postgres-data"
    init = database["spec"]["template"]["spec"]["initContainers"][0]
    assert "chown 70:70" in init["command"][-1]


def test_deploy_script_creates_the_secret_without_applying_the_example():
    script = (ROOT / "scripts" / "k8s-deploy.sh").read_text()
    assert "secret.example.yaml" not in script
    assert "create secret generic taskflow-db" in script
    assert "echo \"$password\"" not in script
    assert "echo '$password'" not in script
    clean = (ROOT / "scripts" / "k8s-clean.sh").read_text()
    assert "delete namespace taskflow" in clean


def test_compose_frontend_proxy_is_unchanged():
    nginx = (ROOT / "taskflow" / "frontend" / "nginx.conf").read_text()
    compose = (ROOT / "taskflow" / "docker-compose.yml").read_text()
    assert "api:8000" in nginx
    assert "taskflow-api" not in nginx
    assert "container_name: taskflow-api" in compose
    assert "image: taskflow-api:local" in compose
    assert "image: taskflow-frontend:local" in compose
