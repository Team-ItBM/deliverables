provider "aws" {
  region  = var.region
  profile = var.aws_profile

  allowed_account_ids = [var.account_id]

  default_tags {
    tags = local.default_tags
  }
}

# CloudFront requires its ACM certificate and its WAF web ACL (scope CLOUDFRONT)
# to be created in us-east-1. Nothing else is created in this region.
provider "aws" {
  alias   = "us_east_1"
  region  = "us-east-1"
  profile = var.aws_profile

  allowed_account_ids = [var.account_id]

  default_tags {
    tags = local.default_tags
  }
}
