# Skeleton — replace with provider-specific resource (aws_eks_cluster, alicloud_cs_managed_kubernetes, etc.)
variable "environment" { type = string }
variable "region"      { type = string }

# Example — keep commented until provider is chosen.
# resource "aws_eks_cluster" "this" {
#   name     = "wcp-${var.environment}"
#   role_arn = "CHANGE_ME"
#   version  = "1.30"
#   vpc_config { subnet_ids = ["CHANGE_ME"] }
# }

output "kubeconfig_command" {
  value = "echo CHANGE_ME — run aws eks update-kubeconfig / aliyun cs ..."
}
