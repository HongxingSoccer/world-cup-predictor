# Skeleton — managed PostgreSQL 16, multi-AZ, encrypted at rest.
variable "environment" { type = string }
variable "region"      { type = string }

# resource "aws_db_instance" "wcp" {
#   identifier            = "wcp-${var.environment}"
#   engine                = "postgres"
#   engine_version        = "16"
#   instance_class        = "db.t4g.large"
#   allocated_storage     = 100
#   storage_encrypted     = true
#   multi_az              = var.environment == "production"
#   backup_retention_period = 7
#   deletion_protection   = true
# }

output "endpoint" { value = "CHANGE_ME-rds-endpoint" }
