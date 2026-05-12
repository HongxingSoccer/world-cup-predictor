# world-cup-predictor

Hongxing Gang

## Repository Architecture

This is the application code repository. Infrastructure, deployment
manifests, and AMI builds live in separate repositories.

| Repo | Role |
|---|---|
| [`world-cup-predictor`](https://github.com/HongxingSoccer/world-cup-predictor) (this) | Application source code, Dockerfiles, docker-compose |
| [`worldcup-terraform`](https://github.com/HongxingSoccer/worldcup-terraform) | AWS infrastructure (VPC, EKS, RDS, S3, IAM) |
| [`worldcup-helm`](https://github.com/HongxingSoccer/worldcup-helm) | Kubernetes Helm charts |
| [`worldcup-packer`](https://github.com/HongxingSoccer/worldcup-packer) | EKS node AMI build templates |

## Image-tag contract

- `ci-build.yml` builds container images and tags them `${git_sha_short}` (7 chars)
- Images are pushed to ECR repositories: `wcp-{ml-api,java-api,frontend,card-worker}`
- After a successful build on `main`, `ci-build.yml` fires a
  `repository_dispatch` to `worldcup-helm`'s `cd-dev.yml`, passing the tag.
  That workflow runs `helm upgrade --install wcp --set global.image.tag=…`.

## Application docs

Per-service documentation lives in [`worldcup-predictor/README.md`](worldcup-predictor/README.md).
