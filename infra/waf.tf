# WAF for CloudFront (scope CLOUDFRONT must be created in us-east-1).
# Rate rules are per source IP (ARCHITECTURE 5절 과부하 방지, 2026-11-05 임시값).
# The "all POST" rule also counts POST /api/rooms and generation requests; the
# stricter rules trigger first, so the overlap is harmless.
# Sampled requests and WAF logging are off (they would retain headers such as
# User-Agent, PRIVACY 제11조); CloudWatch metrics stay on.

locals {
  waf_blocked_body_key = "rate_limited"

  waf_rate_rules = {
    room-create = {
      priority = 10
      limit    = var.waf_room_create_limit
      window   = 600
      block    = true
      path     = { type = "exact", value = "/api/rooms" }
      post     = true
    }
    generation = {
      priority = 20
      limit    = var.waf_generation_limit
      window   = 600
      block    = true
      path     = { type = "regex", value = "^/api/rooms/[^/]+/(generate|retry|regenerate)$" }
      post     = true
    }
    api-post = {
      priority = 30
      limit    = var.waf_post_limit
      window   = 300
      block    = true
      path     = { type = "prefix", value = "/api/" }
      post     = true
    }
    api-all = {
      priority = 40
      limit    = var.waf_api_limit
      window   = 300
      block    = var.waf_api_limit_block
      path     = { type = "prefix", value = "/api/" }
      post     = false
    }
  }
}

resource "aws_wafv2_web_acl" "main" {
  provider = aws.us_east_1

  name        = "${local.name}-cdn"
  description = "Rate limits for dowonpact CloudFront"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  custom_response_body {
    key          = local.waf_blocked_body_key
    content_type = "APPLICATION_JSON"
    content      = jsonencode({ error = "rate_limited", message = "Too many requests. Please try again later." })
  }

  dynamic "rule" {
    for_each = var.waf_enable_common_rule_set ? [1] : []
    content {
      name     = "aws-common-rule-set"
      priority = 1

      override_action {
        count {}
      }

      statement {
        managed_rule_group_statement {
          vendor_name = "AWS"
          name        = "AWSManagedRulesCommonRuleSet"
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${local.name}-common"
        sampled_requests_enabled   = false
      }
    }
  }

  dynamic "rule" {
    for_each = local.waf_rate_rules
    content {
      name     = "rate-${rule.key}"
      priority = rule.value.priority

      action {
        dynamic "block" {
          for_each = rule.value.block ? [1] : []
          content {
            custom_response {
              response_code            = 429
              custom_response_body_key = local.waf_blocked_body_key
            }
          }
        }
        dynamic "count" {
          for_each = rule.value.block ? [] : [1]
          content {}
        }
      }

      statement {
        rate_based_statement {
          limit                 = rule.value.limit
          evaluation_window_sec = rule.value.window
          aggregate_key_type    = "IP"

          scope_down_statement {
            and_statement {
              # 1) HTTP method (POST rules) or a match-all placeholder for the all-/api rule
              statement {
                byte_match_statement {
                  search_string         = rule.value.post ? "POST" : "/api/"
                  positional_constraint = rule.value.post ? "EXACTLY" : "STARTS_WITH"
                  field_to_match {
                    dynamic "method" {
                      for_each = rule.value.post ? [1] : []
                      content {}
                    }
                    dynamic "uri_path" {
                      for_each = rule.value.post ? [] : [1]
                      content {}
                    }
                  }
                  text_transformation {
                    priority = 0
                    type     = "NONE"
                  }
                }
              }

              # 2) Path
              dynamic "statement" {
                for_each = rule.value.path.type == "regex" ? [] : [1]
                content {
                  byte_match_statement {
                    search_string         = rule.value.path.value
                    positional_constraint = rule.value.path.type == "exact" ? "EXACTLY" : "STARTS_WITH"
                    field_to_match {
                      uri_path {}
                    }
                    text_transformation {
                      priority = 0
                      type     = "NONE"
                    }
                  }
                }
              }
              dynamic "statement" {
                for_each = rule.value.path.type == "regex" ? [1] : []
                content {
                  regex_match_statement {
                    regex_string = rule.value.path.value
                    field_to_match {
                      uri_path {}
                    }
                    text_transformation {
                      priority = 0
                      type     = "NONE"
                    }
                  }
                }
              }
            }
          }
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${local.name}-rate-${rule.key}"
        sampled_requests_enabled   = false
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-cdn"
    sampled_requests_enabled   = false
  }
}
