# Skeleton — CDN distribution fronting both the frontend and OSS card bucket.
variable "environment" { type = string }
variable "origin_host" { type = string }
output "domain" { value = "CHANGE_ME-cdn-domain" }
