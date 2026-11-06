# 관리자 접속기록 (ARCHITECTURE 8절, PRIVACY 제10조 3항, 개인정보의 안전성 확보조치 기준 제8조).
# 2026-11-05 팀 결정. 두 가지 기록을 한 버킷에 1년 이상 보관한다.
#   1. CloudTrail 관리 이벤트(모든 리전, 읽기·쓰기): 콘솔 로그인, RDS·ECS·Secrets Manager·IAM 조작, 일회성 태스크 실행.
#   2. 앱의 방 삭제 명령 기록(admin.py가 admin-audit/ 접두사에 JSON 한 건씩 쓴다. 이름·메모는 없다).
# 관리자는 DB에 직접 접속하지 않는다는 전제다. 필요해지면 별도 기록 방안을 정한다.
# 버킷은 서비스 종료 정리(2027-01-12)에서 남긴다. 절차는 README "정리"에 있다.

locals {
  audit_bucket_name  = coalesce(var.audit_bucket_name, "${var.project}-audit-${var.account_id}")
  audit_app_prefix   = "admin-audit/"
  audit_trail_prefix = "cloudtrail"
}

resource "aws_s3_bucket" "audit" {
  bucket = local.audit_bucket_name

  lifecycle {
    prevent_destroy = true # 기록은 마지막 기록 뒤 1년 이상 남는다. 정리 절차는 README.
  }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration {
    status = "Enabled"
  }
}

# 현재 버전과 이전 버전 모두 보관 기간(기본 400일 = 1년 + 여유) 뒤에 지운다. 만료된 삭제 마커와 미완성 업로드도 정리한다.
resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket     = aws_s3_bucket.audit.id
  depends_on = [aws_s3_bucket_versioning.audit]

  rule {
    id     = "expire-after-retention"
    status = "Enabled"
    filter {}

    expiration {
      days = var.audit_retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = var.audit_retention_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "clean-expired-delete-markers"
    status = "Enabled"
    filter {}

    expiration {
      expired_object_delete_marker = true
    }
  }
}

data "aws_iam_policy_document" "audit_bucket" {
  # CloudTrail가 버킷 ACL을 읽고 자기 접두사에만 쓴다.
  statement {
    sid       = "CloudTrailAclCheck"
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.audit.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudtrail:${var.region}:${var.account_id}:trail/${local.name}-audit"]
    }
  }
  statement {
    sid       = "CloudTrailWrite"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.audit.arn}/${local.audit_trail_prefix}/AWSLogs/${var.account_id}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudtrail:${var.region}:${var.account_id}:trail/${local.name}-audit"]
    }
  }
  # HTTPS 요청만 허용한다.
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.audit.arn,
      "${aws_s3_bucket.audit.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "audit" {
  bucket     = aws_s3_bucket.audit.id
  policy     = data.aws_iam_policy_document.audit_bucket.json
  depends_on = [aws_s3_bucket_public_access_block.audit]
}

# 관리 이벤트의 첫 사본은 무료다. 데이터 이벤트와 Insights는 켜지 않는다.
resource "aws_cloudtrail" "audit" {
  name                          = "${local.name}-audit"
  s3_bucket_name                = aws_s3_bucket.audit.id
  s3_key_prefix                 = local.audit_trail_prefix
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true
  enable_logging                = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }

  depends_on = [aws_s3_bucket_policy.audit]
}

# 앱 태스크 역할: 삭제 명령 기록을 admin-audit/ 접두사에만 쓸 수 있다. 읽기·삭제 권한은 없다.
data "aws_iam_policy_document" "ecs_task_audit" {
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.audit.arn}/${local.audit_app_prefix}*"]
  }
}

resource "aws_iam_role_policy" "ecs_task_audit" {
  name   = "write-admin-audit"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task_audit.json
}
