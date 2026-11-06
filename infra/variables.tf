variable "account_id" {
  description = "AWS account this configuration may touch (allowed_account_ids guard). Set in terraform.tfvars (gitignored)."
  type        = string
}

variable "aws_profile" {
  description = "AWS CLI profile. Set to null when credentials come from the environment."
  type        = string
  default     = "itbm"
  nullable    = true
}

variable "region" {
  description = "Primary region. PRIVACY 제5조 fixes Seoul."
  type        = string
  default     = "ap-northeast-2"
}

variable "project" {
  description = "Name prefix for resources."
  type        = string
  default     = "dowonpact"
}

variable "domain_name" {
  description = "Apex domain served by CloudFront."
  type        = string
  default     = "dowonpact.com"
}

variable "hosted_zone_id" {
  description = "Existing Route 53 public hosted zone (created with the domain registration). Read only, never managed here. Set in terraform.tfvars (gitignored)."
  type        = string
}

variable "enable_www_redirect" {
  description = "Serve www.<domain> on the same distribution and 301 it to the apex."
  type        = bool
  default     = true
}

variable "origin_subdomain" {
  description = "Subdomain aliased to the ALB so CloudFront can verify the ALB certificate. Direct requests without the origin header get 403."
  type        = string
  default     = "origin"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "availability_zones" {
  description = "Two AZs. The ALB and the RDS subnet group both require two."
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

# ---- ECS ----

variable "app_desired_count" {
  description = "Fargate task count. Use 0 for the first apply (no image in ECR yet), then 2."
  type        = number
  default     = 2
}

variable "app_cpu" {
  type    = number
  default = 512
}

variable "app_memory" {
  type    = number
  default = 1024
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "health_check_path" {
  description = "Server health endpoint (to be provided by travel.server.main)."
  type        = string
  default     = "/api/health"
}

variable "image_tag" {
  description = "Image tag for the Terraform-managed task definition revision. CI registers later revisions tagged with the git SHA."
  type        = string
  default     = "bootstrap"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention. ARCHITECTURE 5절, PRIVACY 제3조: 30 days."
  type        = number
  default     = 30
}

# ---- RDS ----

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_engine_version" {
  type    = string
  default = "16"
}

variable "db_name" {
  type    = string
  default = "dowonpact"
}

variable "db_username" {
  type    = string
  default = "dowonpact_app"
}

variable "db_backup_retention_days" {
  description = "Automated backups. PRIVACY 제3조, 제7조: 7 days."
  type        = number
  default     = 7
}

variable "db_deletion_protection" {
  description = "Set false and apply only as the first teardown step."
  type        = bool
  default     = true
}

variable "db_skip_final_snapshot" {
  description = "true skips the final snapshot on destroy (team decision 2026-11-05: PRIVACY 제7조 deletes backups within 7 days of service end). Accidental destroy is guarded by db_deletion_protection instead."
  type        = bool
  default     = true
}

# ---- Secrets ----

variable "secret_recovery_window_days" {
  description = "Secrets Manager deletion delay on destroy (0 or 7..30). 7 keeps teardown inside the 2027-01-12 deadline when destroyed on 2027-01-05."
  type        = number
  default     = 7
}

# ---- WAF (ARCHITECTURE 5절 과부하 방지, 2026-11-05 임시값, per IP) ----

variable "waf_room_create_limit" {
  description = "POST /api/rooms per IP per 10 minutes."
  type        = number
  default     = 10
}

variable "waf_generation_limit" {
  description = "POST /api/rooms/{code}/(generate|retry|regenerate) combined, per IP per 10 minutes."
  type        = number
  default     = 10
}

variable "waf_post_limit" {
  description = "POST /api/* per IP per 5 minutes."
  type        = number
  default     = 300
}

variable "waf_api_limit" {
  description = "All /api/* per IP per 5 minutes."
  type        = number
  default     = 3000
}

variable "waf_api_limit_block" {
  description = "false = COUNT mode for the all-/api/* rule (first deploy). Switch to true after reviewing metrics."
  type        = bool
  default     = false
}

variable "waf_enable_common_rule_set" {
  description = "Add AWSManagedRulesCommonRuleSet in COUNT mode (extra per-rule WAF charge)."
  type        = bool
  default     = false
}

# ---- CloudFront response headers ----

variable "csp_enforce" {
  description = "true enforces the CSP in local.content_security_policy. false sends the same value as Content-Security-Policy-Report-Only (README 응답 헤더와 CSP)."
  type        = bool
  default     = true
}

# ---- Alarms ----

variable "alert_email" {
  description = "Address subscribed to the alarm topic. null creates no subscription. Set in terraform.tfvars (gitignored). The value also lands in Terraform state."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}

# ---- S3 ----

variable "spa_bucket_force_destroy" {
  description = "Allow terraform destroy to empty the SPA bucket (static build output only)."
  type        = bool
  default     = true
}

# ---- GitHub OIDC ----

variable "github_repository" {
  description = "Repository part of the GitHub OIDC subject. This repository uses immutable subjects: owner@owner_id/repo@repo_id."
  type        = string
  default     = "Team-ItBM@326874376/deliverables@1362404898"
}

variable "github_deploy_ref" {
  type    = string
  default = "refs/heads/main"
}

variable "create_github_oidc_provider" {
  description = "false if token.actions.githubusercontent.com already exists in the account (none existed on 2026-11-05)."
  type        = bool
  default     = true
}

variable "audit_bucket_name" {
  description = "관리자 접속기록 버킷 이름. null이면 <project>-audit-<account_id>."
  type        = string
  default     = null
  nullable    = true
}

variable "audit_retention_days" {
  description = "접속기록 보관 일수(현재·이전 버전 모두). 1년 이상이어야 한다(PRIVACY 제10조 3항). 기본 400일."
  type        = number
  default     = 400
  validation {
    condition     = var.audit_retention_days >= 365
    error_message = "접속기록은 1년(365일) 이상 보관해야 한다."
  }
}
