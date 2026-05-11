# Helm charts (Phase 4)

These charts make the project deployable to EKS. They are **static**: no
chart in this directory is auto-installed by anything yet. Phase 0 (cloud
infra) provisions the EKS cluster + RDS / ElastiCache / MSK / S3 / ECR /
ACM cert; Phase 5 (CD) will wire `helm upgrade --install` into GitHub
Actions. Until then, charts are validated by `helm lint` + `helm template`
+ `kubeconform` in CI only.

## Layout

```
deploy/charts/
├── README.md              ← this file
├── wcp/                   ← umbrella (Helm dependency on the 4 below)
├── wcp-frontend/          ← Next.js (Deployment + Service + HPA + PDB + SA)
├── wcp-java-api/          ← Spring Boot (same, plus startupProbe + JWT secret mount)
├── wcp-ml-api/            ← FastAPI (same, plus IRSA-bound SA)
└── wcp-workers/           ← 5 Celery Deployments + Flower + MLflow + KEDA
```

## Local validation

```bash
cd deploy/charts/wcp
helm dependency update                # pulls 4 sibling charts into ./charts/
helm lint .                            # umbrella
helm lint ../wcp-frontend ../wcp-java-api ../wcp-ml-api ../wcp-workers

# Render against both envs.
helm template wcp . -f values-dev.yaml  > /tmp/rendered-dev.yaml
helm template wcp . -f values-demo.yaml > /tmp/rendered-demo.yaml

# Schema-check (KEDA + ESO CRDs come from the datreeio catalog).
kubeconform \
  -strict -summary -ignore-missing-schemas \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
  /tmp/rendered-dev.yaml
```

Expected: `37 resources found in 1 file - Valid: 37, Invalid: 0`.

## Install (only once an EKS cluster exists)

```bash
export GIT_SHA=$(git rev-parse --short HEAD)
helm upgrade --install wcp deploy/charts/wcp \
  -n wcp-dev --create-namespace \
  -f deploy/charts/wcp/values-dev.yaml \
  --set global.image.tag=$GIT_SHA \
  --wait
```

## Cluster prerequisites

The charts emit CRs that assume the following are already running:

| Component | Why | CRDs we use |
|---|---|---|
| **AWS Load Balancer Controller** | ALB provisioning for the Ingress | `Ingress` annotations |
| **External Secrets Operator** | Pull from AWS Secrets Manager | `ExternalSecret` |
| **KEDA** | Queue-depth-driven HPA for workers | `ScaledObject`, `TriggerAuthentication` |
| **metrics-server** | CPU HPA on frontend / java-api / ml-api | `HorizontalPodAutoscaler` |
| **cert-manager** (optional) | Webhook certs for some controllers | — |

A `ClusterSecretStore` named `aws-secretsmanager` must exist; the umbrella's
`ExternalSecret` resources reference it by name. The store should be pointed
at AWS Secrets Manager with read access scoped to `/wcp/<env>/*`.

## AWS Secrets Manager paths consumed

The umbrella's `ExternalSecret` resources read these keys from
AWS Secrets Manager (prefixed `/wcp/<env>/`):

```
db/url                       → DATABASE_URL
db/password                  → SPRING_DATASOURCE_PASSWORD
redis/url                    → REDIS_URL
kafka/brokers                → KAFKA_BROKERS
api-key-internal             → API_KEY, ML_API_KEY
admin-api-token              → ADMIN_API_TOKEN
stripe/secret-key            → STRIPE_SECRET_KEY
stripe/webhook-secret        → STRIPE_WEBHOOK_SECRET
api-football-key             → API_FOOTBALL_KEY
odds-api-key                 → ODDS_API_KEY
anthropic-api-key            → ANTHROPIC_API_KEY
mlflow/backend-store-uri     → MLFLOW_BACKEND_STORE_URI
jwt/private-key              → wcp-jwt-keys: jwt-private.pem
jwt/public-key               → wcp-jwt-keys: jwt-public.pem
```

Terraform / a manual operator must create these before the first install.

## IRSA role placeholders

`values-{env}.yaml` leaves every `eks.amazonaws.com/role-arn` empty.
Phase 0 Terraform produces these ARNs and the CD pipeline injects them
via `--set`.

| ServiceAccount | Required AWS access |
|---|---|
| `wcp-frontend` | — (none) |
| `wcp-java-api` | Secrets Manager: read `/wcp/<env>/*` |
| `wcp-ml-api` | Secrets Manager + S3 `wcp-mlflow-artifacts/*` |
| `wcp-workers` | Secrets Manager + S3 `wcp-mlflow-artifacts/*` |
| `wcp-mlflow` | S3 `wcp-mlflow-artifacts/*` |

## Sizing baseline

Inherited from `deploy-recon/13_runtime_resources.md §13.5`. Tweaks are
documented inline in each chart's `values.yaml`.

## What's deliberately not here

- No Helm hooks (no DB migrations yet — Flyway moves into Phase 5)
- No Prometheus / Grafana / CloudWatch agent charts (separate phase)
- No NetworkPolicy / Calico rules (separate phase)
- No CRDs for KEDA / ESO / ALB controller (these are installed cluster-wide,
  not per-app)
