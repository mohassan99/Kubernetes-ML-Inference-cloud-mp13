# Two-Tier ML Inference on Kubernetes (AWS EKS)

A microservice architecture for serving ML models behind a single load-balanced API on AWS EKS, with namespace-level tenant isolation and per-tier resource quotas. Two model-serving tiers (free: feedforward NN on MNIST; premium: CNN on KMNIST) demonstrate the deployment pattern used by ML platforms that serve multiple model versions, customer segments, or business lines from a shared cluster.

Built for CS 498 Cloud Computing Applications (UIUC, MCS).

## Why this pattern matters for ML / healthcare ML

Production ML rarely lives or dies on the model itself — it lives or dies on how the model gets served, scaled, and isolated. This project implements the deployment scaffolding that real ML platforms (especially in regulated industries like healthcare and payer analytics) need:

- **Tenant isolation** via Kubernetes namespaces — analogous to keeping different lines of business (commercial vs Medicaid vs Medicare), different model versions, or different customer cohorts cleanly separated on shared infrastructure.
- **Resource governance** via `ResourceQuota` — caps compute and pod counts per tenant, preventing one workload from starving others. The same pattern enforces SLAs across services.
- **Path-based routing** via Envoy — one public entry point, multiple downstream model services. Lets you A/B test model versions or route by request type without exposing the internal topology.
- **Job-based inference** via Kubernetes Jobs — each prediction request spawns a one-shot job that runs the model and exits. Compute is reclaimed after each request, which fits batch-style scoring workloads (claims risk scoring, member stratification, prior-auth ML) better than always-on serving.
- **Namespace-scoped RBAC** — service accounts can only create resources in their own namespace. Aligns with least-privilege requirements common in HIPAA-aware environments.

The models here are simple by design (the project is about the platform, not the models), but the architecture transfers directly to serving healthcare-domain models — claims classification, ICD code prediction, readmission risk, member churn, prior-authorization triage — at scale.

## Architecture

![Architecture](docs/architecture.png)

### How traffic flows

A request from the internet hits the AWS Load Balancer, which forwards it to Envoy. Envoy reads the URL and decides where to send it: `/free` goes to the free-tier Flask app, `/premium` goes to the premium-tier Flask app. The Flask app then creates a Kubernetes Job that runs the actual ML inference (one Job per request) and returns the job name. Envoy is a traffic router commonly used in Kubernetes systems; nginx could play the same role.

## Stack
- **Orchestration:** Amazon EKS, kubectl, eksctl
- **Container runtime:** Docker, DockerHub registry
- **Traffic routing:** Envoy
- **Application:** Python 3.9, Flask, PyTorch
- **Infrastructure:** AWS Network Load Balancer, EC2 (t3.medium nodes)
- **Datasets:** MNIST, KMNIST (used as stand-ins for arbitrary classification models)

## Key engineering decisions
- **Namespace isolation** with per-namespace `ResourceQuota` (free tier capped at 2 CPU / 2 pods) demonstrates multi-tenant resource governance.
- **Job-based inference** (one-shot Kubernetes Jobs vs long-running services) matches the bursty, stateless nature of batch ML scoring and lets the platform garbage-collect compute after each request.
- **Envoy as the entry point** routes by URL path (`/free`, `/premium`) to the right Flask service — single public entry point, internal traffic stays in-cluster.
- **External LoadBalancer Service** maps port 80 → container 8080 (non-root Envoy listener), following standard HTTP conventions for the public surface while respecting Linux's privileged-port rules inside containers.
- **Service accounts with RBAC** scoped to each namespace let the Flask apps create Jobs without granting cluster-wide privileges.

## Repository structure
```
.
├── clusterConfig.yaml              # eksctl cluster definition
├── free_service/
│   ├── app/                         # Flask API + Dockerfile
│   ├── job/                         # Inference Job container
│   ├── free-tier-quota.yaml         # ResourceQuota (2 CPU / 2 pods)
│   ├── free-tier-service.yaml
│   ├── free_deployment.yaml
│   └── free_tier_envoy.yaml
├── premium_service/                 # mirror of free_service (no quota)
├── web_tier/
│   ├── Dockerfile.web-tier          # Envoy container
│   ├── web_tier_envoy.yaml          # routing config
│   └── web_tier_deployment.yaml     # Deployment + LoadBalancer Service
├── model_config/                    # PyTorch training & inference code
├── grader_interface.py              # Flask wrapper exposing kubectl state
└── submit.py                        # autograder client
```

## Deployment

```bash
# 1. Create the cluster
eksctl create cluster -f clusterConfig.yaml

# 2. Build and push images
docker build -t <user>/free-tier-app:latest -f free_service/app/Dockerfile.free-tier-app free_service/app
docker build -t <user>/free-tier-job:latest -f free_service/job/Dockerfile.free-tier-job free_service/job
# (same for premium-tier-app, premium-tier-job, web-tier)
docker push <user>/free-tier-app:latest
# (push the rest)

# 3. Apply manifests
kubectl apply -f free_service/free-tier-quota.yaml
kubectl apply -f free_service/free_deployment.yaml
kubectl apply -f free_service/free-tier-service.yaml
kubectl apply -f premium_service/premium_deployment.yaml
kubectl apply -f premium_service/premium-tier-service.yaml
kubectl apply -f web_tier/web_tier_deployment.yaml

# 4. Verify
kubectl get svc -n web-tier
# EXTERNAL-IP -> AWS NLB DNS
```

## Sample request
```bash
curl -X POST http://<LB-DNS>/free \
  -H "Content-Type: application/json" \
  -d '{"dataset":"mnist"}'
# {"job_name":"free-job-template-...","status":"submitted"}
```

## Tested
4/4 autograder tests passing — POST `/free`, GET `/free/resource-quota`, end-to-end free-tier Job, end-to-end premium-tier Job + log retrieval.
