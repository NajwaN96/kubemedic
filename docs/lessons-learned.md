# Lessons learned

These came out of running the lab, not from a checklist.

## Events outlive the failure

A Kubernetes event can still say CrashLoopBackOff after the new Pod is healthy. Using every stored event as proof that the incident is ongoing keeps resolved work open. The freshness window keeps the event in the evidence and ignores it for liveness of the incident.

## A missing Pod is not recovery

The object can disappear because it was deleted, because the informer missed a beat, or because the workload was removed. Treating absence as success marks incidents resolved while the Deployment is still down. The orphan path asks whether the owner is healthy, waits out the stabilization window, and writes a reason. If the owner is gone too, the reason says the resource no longer exists. The evidence stays.

## Ready replicas did not prove the rollback ran

REM-000001 and REM-000002 on INV-000019 were stored as verified while the API Deployment stayed on generation 3. The crashing command was still there. `readyReplicas` was 2 because the previous Pods were still up. `updatedReplicas` was 1.

The client called `patch_namespaced_deployment` with a strategic-merge body. The Python client default content type is `application/json-patch+json`, so the API server did not apply that body. The old ready Pods made the check look healthy.

The fix is in the executor and the runner:

- set the patch content type explicitly
- rollback is one JSON patch, `replace /spec/template`, built inside the executor
- the runner fails the attempt if generation does not increase
- recovery requires updated replicas at or above desired, and `observedGeneration` at or above generation

REM-000003 is the attempt that passed those checks: generation 3 to 4, revision 4, both Pods updated and ready.

Succeeded means the API accepted the patch and generation advanced. Verified means the new Pods became ready. Those are different states. A verified record whose generation did not change can be superseded. A failed record is not retried by itself. A verified change that did move generation stays.

## AI is not the operational record

Every stored investigation in this cluster has `analysis_source` `rules`. The AI client exists and is tested with fakes. No live OpenAI call was made. When the provider is down, the rules still classify, still track recovery, and still propose the typed action.

## Metrics and investigations answer different questions

Prometheus shows that error rate rose or that ready replicas fell. It does not store the command that was patched onto the Pod, the event text, or who approved the rollback. KubeMedic stores that record. It does not replace the dashboards.

## Least privilege matters more once something can write

A read-only watcher can be wrong and the cluster is unchanged. A remediator that can patch arbitrary JSON, exec, or delete namespaces is a shell with extra steps. The write role is Deployments only, the action names are fixed, the scale range is 1 to 5, and the patch document is built in code.

## A cloud design can stay on paper

The EKS module is real HCL. It is also behind a count of zero, a NAT validation that rejects true, and a CI script that refuses plan and apply. That is the cost control. Describing the architecture does not require creating it.
