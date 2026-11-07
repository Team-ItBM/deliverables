locals {
  name = var.project

  default_tags = {
    Project = "dowonpact"
    Owner   = "ItBM"
  }

  origin_domain = "${var.origin_subdomain}.${var.domain_name}"
  www_domain    = "www.${var.domain_name}"
  cdn_aliases   = var.enable_www_redirect ? [var.domain_name, local.www_domain] : [var.domain_name]

  container_name = "app"

  # Secrets Manager secret names. Values are set by a human, except db (Terraform writes it).
  secret_names = {
    openai        = "${var.project}/openai-api-key"
    vapid         = "${var.project}/vapid"
    db            = "${var.project}/db"
    origin_verify = "${var.project}/origin-verify"
  }

  # Container environment contract. Names are provisional until the team lead
  # confirms them with the server implementer; rename here only.
  app_env_plain = {
    PUBLIC_BASE_URL    = "https://${var.domain_name}"
    LLM_MODE           = "live"
    AWS_REGION         = var.region
    ADMIN_AUDIT_BUCKET = local.audit_bucket_name
    ADMIN_AUDIT_PREFIX = local.audit_app_prefix
  }

  # env var name => valueFrom (secret ARN, or ARN:json-key:: for JSON secrets)
  app_env_secrets = {
    OPENAI_API_KEY    = aws_secretsmanager_secret.openai.arn
    VAPID_PUBLIC_KEY  = "${aws_secretsmanager_secret.vapid.arn}:public_key::"
    VAPID_PRIVATE_KEY = "${aws_secretsmanager_secret.vapid.arn}:private_key::"
    VAPID_SUBJECT     = "${aws_secretsmanager_secret.vapid.arn}:subject::"
    DATABASE_URL      = aws_secretsmanager_secret.db.arn
  }

  # Schema init command run as a one-off task by CI (assumed; the server implementer must match it).
  db_init_command = ["python", "-m", "travel.server.db", "--init"]
}
