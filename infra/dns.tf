data "aws_route53_zone" "main" {
  zone_id = var.hosted_zone_id
}

# ---- ACM: CloudFront certificate (must be us-east-1) ----

resource "aws_acm_certificate" "cdn" {
  provider = aws.us_east_1

  domain_name               = var.domain_name
  subject_alternative_names = var.enable_www_redirect ? [local.www_domain] : []
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# ---- ACM: ALB certificate (Seoul) for origin.<domain> ----

resource "aws_acm_certificate" "origin" {
  domain_name       = local.origin_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

locals {
  cert_validation_records = merge(
    { for dvo in aws_acm_certificate.cdn.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    } },
    { for dvo in aws_acm_certificate.origin.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    } },
  )
}

resource "aws_route53_record" "cert_validation" {
  for_each = local.cert_validation_records

  zone_id         = data.aws_route53_zone.main.zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 300
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "cdn" {
  provider = aws.us_east_1

  certificate_arn = aws_acm_certificate.cdn.arn
  validation_record_fqdns = [
    for d in aws_acm_certificate.cdn.domain_validation_options : aws_route53_record.cert_validation[d.domain_name].fqdn
  ]
}

resource "aws_acm_certificate_validation" "origin" {
  certificate_arn = aws_acm_certificate.origin.arn
  validation_record_fqdns = [
    for d in aws_acm_certificate.origin.domain_validation_options : aws_route53_record.cert_validation[d.domain_name].fqdn
  ]
}

# ---- Records ----

resource "aws_route53_record" "apex" {
  for_each = toset(["A", "AAAA"])

  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = each.value

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "www" {
  for_each = var.enable_www_redirect ? toset(["A", "AAAA"]) : toset([])

  zone_id = data.aws_route53_zone.main.zone_id
  name    = local.www_domain
  type    = each.value

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "origin" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = local.origin_domain
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = false
  }
}
