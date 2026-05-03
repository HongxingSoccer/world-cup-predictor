# Root Terraform module (Phase 5, design §2.1).
#
# This is a skeleton that wires together cloud-agnostic modules:
#   - k8s-cluster: managed Kubernetes (EKS / ACK / GKE — provider TBD)
#   - rds:        managed PostgreSQL 16 (multi-AZ, encrypted at rest)
#   - redis:      managed Redis 7 (cluster mode disabled, replicated)
#   - oss:        object storage for cards + ml-artifacts
#   - cdn:        edge cache for the frontend + share cards
#
# The provider block is intentionally empty: pick aws/alicloud/google before
# applying. CHANGE_ME tokens mark every value that must be filled per env.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    # Example — uncomment the provider you want.
    # aws       = { source = "hashicorp/aws", version = "~> 5.0" }
    # alicloud  = { source = "aliyun/alicloud", version = "~> 1.220" }
    # google    = { source = "hashicorp/google", version = "~> 5.0" }
  }
  backend "s3" {
    # bucket  = "CHANGE_ME-tfstate"
    # key     = "wcp/terraform.tfstate"
    # region  = "CHANGE_ME"
    # encrypt = true
  }
}

variable "environment" {
  type        = string
  description = "staging | production"
}

variable "region" {
  type    = string
  default = "CHANGE_ME"
}

module "k8s_cluster" {
  source      = "./modules/k8s-cluster"
  environment = var.environment
  region      = var.region
}

module "rds" {
  source      = "./modules/rds"
  environment = var.environment
  region      = var.region
}

module "redis" {
  source      = "./modules/redis"
  environment = var.environment
  region      = var.region
}

module "oss" {
  source      = "./modules/oss"
  environment = var.environment
}

module "cdn" {
  source      = "./modules/cdn"
  environment = var.environment
  origin_host = module.oss.public_endpoint
}

output "kubeconfig_command" {
  value = module.k8s_cluster.kubeconfig_command
}
