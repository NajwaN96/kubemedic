# Threat model

Scope is this lab repository and the local kind cluster. There is no multi-tenant production deployment.

| Risk | What the repo does | What remains |
| --- | --- | --- |
| Secret values in logs or evidence | Log and event text is redacted before it is stored. The watcher cannot `get` Secrets. The audit snapshot keeps images, replicas, revision, and generation | Redaction is pattern-based. A novel secret format can still slip through. Do not rely on it as a vault |
| Secret values sent to an AI provider | AI is off by default. The payload builder runs the sanitizer and sends a bounded subset. The provider is not given a kubeconfig | A person who enables AI is sending operational text to that provider. Review the payload before you do that |
| Overprivileged ServiceAccount | The watcher role is get, list, and watch on pods, events, PVCs, pod logs, Deployments, and ReplicaSets in `taskflow`. The remediator may patch and update Deployments and may read ReplicaSets. No wildcard, no secrets, no exec, no delete, no ClusterRole for KubeMedic | Prometheus has a read-only ClusterRole so it can scrape nodes and cAdvisor through the API. That is broader than KubeMedic and still cannot write |
| Malicious remediation request | Flag defaults false. Approval requires confirm, a short name, and a reason. The action must be one of three names. Scale must be an integer from 1 to 5. The namespace must be the watched namespace | Anyone who can reach the API while the flag is on can approve. The lab API is not authenticated. Do not expose it beyond localhost |
| Duplicate approval | A second proposal for the same investigation, action, and target is not created while one is in progress or has truly changed the Deployment | A verified no-op can be superseded. That path exists so the generation bug can be corrected. It should not be treated as a retry button for real failures |
| Arbitrary patch or shell | The HTTP API does not accept a patch body, a shell command, or a YAML document. Rollback builds `replace /spec/template` in the executor | A bug in that builder would still be a write. Tests cover the content type and the generation check |
| Cross-namespace mutation | Proposals are dropped when the namespace is not the configured one. The remediator role exists only in `taskflow` | The flag does not add a second namespace. Cluster-wide write was never granted |
| Unsafe scale | Values outside 1 to 5 are rejected. `desired == 0` proposes scale to 1, not to the previous size | The previous size is not restored automatically. That is deliberate |
| GitHub token or cloud key in Git | gitleaks runs in CI and was run locally. `.env`, tfstate, and kubeconfig are gitignored. Examples are placeholders | Allowlisted test fixtures contain fake secrets on purpose. A real key pasted into a fixture path would be skipped. Keep real keys out of those paths |
| Accidental `terraform apply` | The platform module is omitted unless both cost gates are set. NAT cannot be enabled by a variable. Node desired size must stay 0. CI refuses plan and apply. State is local and gitignored | The HCL still describes billable resources. Someone who edits the gates and applies them will create an EKS control plane and start a bill. Do not do that for this portfolio |
| AI-invented remediation | Proposals are built from the rule finding. AI text is not parsed into actions. The AI package does not call the Kubernetes client | A future change that feeds model output into `propose()` would break this boundary. The tests forbid remediation imports in the AI package |

Out of scope: cluster-admin break-glass for the reference EKS design, network policy inside kind, and authentication on the lab UIs.
