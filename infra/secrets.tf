# Secrets Manager. Only names live in code. Values:
#   dowonpact/openai-api-key  plain string            - set by a human
#   dowonpact/vapid           JSON {public_key, private_key, subject} - set by a human
#   dowonpact/origin-verify   plain random string     - set by a human (README bootstrap)
#   dowonpact/db              plain DATABASE_URL      - written by Terraform from random_password
#
# Chicken-and-egg: CloudFront and the ALB listener rule need the origin-verify
# value at plan time (data source below). The secret must therefore exist and
# hold a value before the full apply. README bootstrap step 2 uses -target to
# create the secrets first.

resource "aws_secretsmanager_secret" "openai" {
  name                    = local.secret_names.openai
  description             = "OpenAI API key for the server (value set manually)"
  recovery_window_in_days = var.secret_recovery_window_days
}

resource "aws_secretsmanager_secret" "vapid" {
  name                    = local.secret_names.vapid
  description             = "Web Push VAPID keys JSON public_key private_key subject (value set manually)"
  recovery_window_in_days = var.secret_recovery_window_days
}

resource "aws_secretsmanager_secret" "origin_verify" {
  name                    = local.secret_names.origin_verify
  description             = "X-Origin-Verify header value shared by CloudFront and the ALB (value set manually)"
  recovery_window_in_days = var.secret_recovery_window_days
}

resource "aws_secretsmanager_secret" "db" {
  name                    = local.secret_names.db
  description             = "PostgreSQL connection URL for the app (written by Terraform)"
  recovery_window_in_days = var.secret_recovery_window_days
}

data "aws_secretsmanager_secret_version" "origin_verify" {
  secret_id = aws_secretsmanager_secret.origin_verify.id
}

# RDS master password: Terraform random_password (not RDS-managed password).
# Reason: the app needs one stable DATABASE_URL secret; the RDS-managed secret is
# JSON {username,password} and rotates every 7 days by default, which would
# leave a derived URL stale. Trade-off: the password is in Terraform state.
resource "random_password" "db" {
  length  = 32
  special = false # URL-safe without percent-encoding
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = format(
    "postgresql://%s:%s@%s:%d/%s?sslmode=require",
    var.db_username,
    random_password.db.result,
    aws_db_instance.main.address,
    aws_db_instance.main.port,
    var.db_name,
  )
}
