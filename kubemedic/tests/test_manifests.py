from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_ROOT = ROOT / "k8s" / "kubemedic"
WRITE_VERBS = {"create", "update", "patch", "delete", "deletecollection", "*"}


def documents():
    found = []
    for path in sorted(MANIFEST_ROOT.rglob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text()):
            if document:
                found.append((path, document))
    return found


def by_kind(kind: str):
    return [doc for _path, doc in documents() if doc.get("kind") == kind]


def one(kind: str, name: str):
    matches = [doc for doc in by_kind(kind) if doc["metadata"]["name"] == name]
    assert len(matches) == 1
    return matches[0]


def test_rbac_is_read_only_and_namespace_scoped():
    observer = one("Role", "kubemedic-observer")
    assert by_kind("ClusterRole") == []
    assert observer["metadata"]["namespace"] == "taskflow"
    for rule in observer["rules"]:
        assert "*" not in rule["resources"]
        assert "secrets" not in rule["resources"]
        assert not WRITE_VERBS.intersection(rule["verbs"])
        assert set(rule["verbs"]).issubset({"get", "list", "watch"})
    log_rules = [rule for rule in observer["rules"] if "pods/log" in rule["resources"]]
    assert log_rules
    assert log_rules[0]["verbs"] == ["get"]


def test_remediator_role_is_separate_and_narrow():
    role = one("Role", "kubemedic-remediator")
    assert role["metadata"]["namespace"] == "taskflow"
    resources = []
    for rule in role["rules"]:
        assert "*" not in rule["resources"]
        assert "secrets" not in rule["resources"]
        assert "pods" not in rule["resources"]
        assert "pods/exec" not in rule["resources"]
        assert "configmaps" not in rule["resources"]
        assert "delete" not in rule["verbs"]
        assert "deletecollection" not in rule["verbs"]
        resources.extend(rule["resources"])
    assert resources == ["deployments", "replicasets"]
    deployment_rule = role["rules"][0]
    assert set(deployment_rule["verbs"]) == {"get", "list", "watch", "patch", "update"}
    assert set(role["rules"][1]["verbs"]) == {"get", "list", "watch"}
    binding = one("RoleBinding", "kubemedic-remediator")
    assert binding["subjects"][0]["name"] == "kubemedic-remediator"
    assert binding["subjects"][0]["namespace"] == "kubemedic"
    observer_binding = one("RoleBinding", "kubemedic-observer")
    assert observer_binding["subjects"][0]["name"] == "kubemedic"


def test_binding_lets_the_kubemedic_account_read_taskflow():
    binding = one("RoleBinding", "kubemedic-observer")
    assert binding["metadata"]["namespace"] == "taskflow"
    assert binding["roleRef"]["kind"] == "Role"
    assert binding["roleRef"]["name"] == "kubemedic-observer"
    subject = binding["subjects"][0]
    assert subject["kind"] == "ServiceAccount"
    assert subject["name"] == "kubemedic"
    assert subject["namespace"] == "kubemedic"


def test_deployment_is_read_only_runtime():
    deployment = one("Deployment", "kubemedic")
    pod = deployment["spec"]["template"]
    assert pod["spec"]["serviceAccountName"] == "kubemedic"
    assert deployment["metadata"]["namespace"] == "kubemedic"
    container = pod["spec"]["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert pod["spec"]["securityContext"]["runAsNonRoot"] is True
    assert pod["spec"]["securityContext"]["runAsUser"] != 0
    mounts = " ".join(str(item) for item in pod["spec"].get("volumes") or [])
    assert "docker.sock" not in mounts
    assert "secretKeyRef" not in yaml.safe_dump(deployment)
    env = {item["name"]: item["value"] for item in container.get("env", []) if "value" in item}
    config = one("ConfigMap", "kubemedic-config")["data"]
    assert config["KUBEMEDIC_NAMESPACE"] == "taskflow"
    assert config["KUBEMEDIC_DEMO_MODE"] == "false"
    assert config["KUBEMEDIC_REMEDIATION_ENABLED"] == "false"
    assert env.get("KUBEMEDIC_NAMESPACE", config["KUBEMEDIC_NAMESPACE"]) == "taskflow"
    remediator = one("Deployment", "kubemedic-remediator")
    remediator_pod = remediator["spec"]["template"]["spec"]
    assert remediator_pod["serviceAccountName"] == "kubemedic-remediator"
    assert remediator_pod["containers"][0]["command"] == ["python", "-m", "app.remediation.runner"]
    assert "secretKeyRef" not in yaml.safe_dump(remediator)
    assert remediator_pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"] is True
    claim = one("PersistentVolumeClaim", "kubemedic-data")
    assert claim["metadata"]["namespace"] == "kubemedic"
