# MLflow artifact root: file:// → S3

## Why the change

The dev `docker-compose.yml` puts MLflow run artifacts (model pickles,
training reports, plots) on a docker named volume `mlflow_artifacts`
mounted by **three** services at once:

- `mlflow-server` (the tracking server) — writes
- `ml-api` (loads `Production` stage models at startup) — reads
- `ingestion-worker` (logs new training runs) — writes

That works locally because docker volumes are `ReadWriteMany` by default.
On EKS, ReadWriteMany filesystems are scarce and expensive (EFS, FSx);
it also violates the 12-factor `IV. Backing services` rule — artifacts
are an object-storage concern.

This doc walks the move to **S3-compatible storage** (MinIO locally, AWS
S3 in production), keeping the local file:// path as the default so
nothing breaks for existing developers.

## What changed in the code

- **None** in Python / Java. Application code uses
  `mlflow.set_tracking_uri()` + `mlflow.log_artifact()` /
  `mlflow.pyfunc.load_model()`, which read the artifact destination
  from the MLflow tracking server. The change is purely operational.

- `docker-compose.yml` now reads
  `MLFLOW_DEFAULT_ARTIFACT_ROOT` from the new env var
  `MLFLOW_ARTIFACT_ROOT`, defaulting to the existing
  `/data/mlflow-artifacts` for backwards compatibility.

- New optional override file `docker-compose.s3.yml` flips
  `MLFLOW_ARTIFACT_ROOT` to `s3://wcp-mlflow-artifacts/` (the local
  MinIO bucket) and injects boto3 + S3 endpoint credentials so the
  tracking server, ml-api, and ingestion-worker can all talk to S3.

## Local dev paths

### Default (unchanged — file:// volume)

```sh
docker compose up -d
# MLflow stores artifacts under /data/mlflow-artifacts (docker volume).
# UI: http://localhost:5001/ (port 5001 because port 5000 is reserved
# by macOS AirPlay; see docker-compose.override.yml).
```

Existing runs in `mlruns/` keep working without any action.

### Opt-in S3 mode (local MinIO)

```sh
docker compose -f docker-compose.yml \
               -f docker-compose.override.yml \
               -f docker-compose.s3.yml \
               up -d
```

After it boots, point the MLflow UI at the same URL — runs created
**before** this switch will still resolve their old `/data/mlflow-artifacts`
URLs (broken inside the container now), but **new** runs will write to
`s3://wcp-mlflow-artifacts/` on MinIO. To migrate the existing artifacts
into the bucket:

```sh
# Make sure the bucket exists
docker run --rm --network worldcup-predictor_default \
           -e MC_HOST_local="http://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@minio:9000" \
           minio/mc mb -p local/wcp-mlflow-artifacts

# Mirror the volume contents into S3 (one-shot)
docker run --rm --network worldcup-predictor_default \
           -v worldcup-predictor_mlflow_artifacts:/src:ro \
           -e MC_HOST_local="http://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@minio:9000" \
           minio/mc mirror /src local/wcp-mlflow-artifacts/
```

## Production (EKS) values

When the helm chart for `mlflow-server` is written, supply these values:

```yaml
mlflow:
  backendStoreUri: postgresql://wcp_mlflow:<REDACTED>@rds-host:5432/mlflow
  artifactRoot: s3://wcp-prod-mlflow-artifacts/
  env:
    # IRSA-based — no static access keys needed
    AWS_DEFAULT_REGION: us-east-1
    # Optional: skip MLFLOW_S3_ENDPOINT_URL entirely so boto3 uses the
    # real AWS endpoint instead of a MinIO override
```

And on every consumer Deployment (`ml-api`, `ingestion-worker`):

```yaml
serviceAccount:
  name: wcp-mlflow-readers   # IRSA-bound to an IAM role with s3:GetObject on the bucket
env:
  - name: MLFLOW_TRACKING_URI
    value: http://mlflow-server.wcp-prod.svc.cluster.local:5000
  - name: AWS_DEFAULT_REGION
    value: us-east-1
# NO MLFLOW_S3_ENDPOINT_URL — boto3 uses AWS S3 directly.
# NO AWS_ACCESS_KEY_ID / SECRET — IRSA provides STS credentials.
```

## Breaking the shared volume in EKS

The `mlflow_artifacts` named volume is mounted by three containers in
the local compose stack:

```
mlflow-server  → /data/mlflow-artifacts (RW)
ml-api         → /data/mlflow-artifacts (R)
ingestion-worker → /data/mlflow-artifacts (RW)
```

EKS helm charts should:

- **Drop the volume mount entirely** from `ml-api` and `ingestion-worker`.
  These read/write through the MLflow tracking server API + boto3, never
  the local filesystem. The local mount only ever existed as a
  performance optimisation for the file:// backend.
- **Drop the volume mount** from `mlflow-server` too once `artifactRoot`
  is `s3://...`.

The new env-driven default keeps the file:// path working unchanged for
existing developers; the helm values simply never set the volume.

## Migration checklist

- [ ] Local: confirm `docker compose -f ... -f docker-compose.s3.yml up` boots
- [ ] Local: confirm MLflow UI lists existing runs + can log a new run
- [ ] Local: `mc ls local/wcp-mlflow-artifacts/` shows the new run's artifact
- [ ] Pre-prod: provision RDS Postgres `mlflow` database (or reuse main RDS)
- [ ] Pre-prod: provision S3 bucket `wcp-prod-mlflow-artifacts`
- [ ] Pre-prod: provision IAM role + IRSA binding for `wcp-mlflow-readers`
- [ ] Pre-prod: mirror `mlruns/` (if any prod-relevant runs exist) to S3
- [ ] Pre-prod: deploy mlflow-server helm chart pointed at S3 backend
- [ ] Pre-prod: smoke `mlflow ui` reachable + `ml-api` loads production model
