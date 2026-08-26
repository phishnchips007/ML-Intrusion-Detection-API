# Local Kubernetes demo

This is a small portfolio proof-of-concept for running the existing FastAPI
container on Kubernetes. A Deployment keeps one copy of the API running as a
Pod. A ClusterIP Service gives that Pod a stable in-cluster address:

```text
curl -> Service:8000 -> Pod -> container:8000 -> FastAPI (/health or /predict)
```

The Service selects the Pod by the `app: mlids-api` label and forwards port
8000 to the container's named `http` port. The Deployment uses the existing
Dockerfile image, `mlids-api:local`; it does not retrain or alter the model or
its 74-feature API contract.

## Key fields

- `replicas: 1` keeps the demo intentionally small.
- `imagePullPolicy: IfNotPresent` lets kind use the image loaded into the node
  without requiring a registry.
- Readiness and liveness both call `/health` on port 8000. Readiness starts
  after 5 seconds and checks every 5 seconds so traffic waits briefly for
  startup; liveness starts after 10 seconds and checks every 10 seconds so a
  slow startup is not restarted prematurely.
- Requests of `100m` CPU and `256Mi` memory reserve modest room for a small
  scikit-learn service. Limits of `500m` CPU and `512Mi` memory bound this demo
  container while leaving room for model loading and one inference request.
- The Pod requires non-root execution, uses the image's `app` user (UID 100,
  with its image group), drops all
  Linux capabilities, disallows privilege escalation, uses the runtime
  default seccomp profile, and has a read-only root filesystem. The image
  sets `PYTHONDONTWRITEBYTECODE=1` and the application only reads its bundled
  model, so no writable application path is needed.

## Reproduce with kind

Run these commands from the repository root. The cluster name is disposable;
use a different name if it already exists.

```bash
docker build -t mlids-api:local .
kind create cluster --name mlids-demo
kind load docker-image mlids-api:local --name mlids-demo
kubectl --context kind-mlids-demo apply --dry-run=server -f k8s/
kubectl --context kind-mlids-demo apply -f k8s/
kubectl --context kind-mlids-demo rollout status deployment/mlids-api --timeout=120s
kubectl --context kind-mlids-demo wait --for=condition=ready pod -l app=mlids-api --timeout=120s
kubectl --context kind-mlids-demo get pods,svc
kubectl --context kind-mlids-demo port-forward service/mlids-api 8000:8000
```

In a second terminal, while the port-forward is running:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  --data-binary @samples/sample_flow.json
```

The sample file is the repository's valid 74-feature request. The exact
prediction is model-artifact dependent; a successful response has HTTP 200
and the existing `prediction`, `class`, and `confidence` fields.

Clean up after the demo:

```bash
kubectl --context kind-mlids-demo delete -f k8s/
kind delete cluster --name mlids-demo
```

No cloud, AWS, or EKS resources are used. Production follow-up work would
include ingress, TLS, secrets management, HPA/autoscaling, multiple replicas
for HA, observability, a service mesh, and Helm packaging. Those are
intentionally outside this minimal demo.

## Validation captured for this change

The manifests passed server-side validation and were exercised through the
Service on kind with the commands above. The relevant output was:

```text
deployment.apps/mlids-api configured (server dry run)
service/mlids-api unchanged (server dry run)
deployment "mlids-api" successfully rolled out
pod/mlids-api-78f678cc95-jgld4 condition met

NAME                             READY   STATUS    RESTARTS   AGE   IP           NODE
pod/mlids-api-78f678cc95-jgld4   1/1     Running   0          32s   10.244.0.6   mlids-demo-control-plane

NAME        TYPE       CLUSTER-IP    EXTERNAL-IP   PORT(S)    AGE   SELECTOR
mlids-api   ClusterIP  10.96.39.96   <none>         8000/TCP   83s   app=mlids-api

--- /health ---
{"status":"healthy"}
--- /predict ---
{"prediction":"ATTACK","class":1,"confidence":1.0}
```
