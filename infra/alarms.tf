# Failure alarms. Thresholds, missing-data choices and their evidence are in
# README 장애 알람.

# Not encrypted: CloudWatch alarms cannot publish to a topic that uses the
# AWS managed key alias/aws/sns, and a customer managed key has a monthly cost.
# Messages carry alarm names and metric values only.
resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

data "aws_iam_policy_document" "alerts_topic" {
  statement {
    sid       = "AllowCloudWatchAlarms"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:cloudwatch:${var.region}:${var.account_id}:alarm:*"]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts_topic.json
}

resource "aws_sns_topic_subscription" "alert_email" {
  count = var.alert_email == null ? 0 : 1

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

locals {
  alarm_actions = [aws_sns_topic.alerts.arn]

  # With no tasks these metrics have no data, so the alarms below that use this
  # count would sit in ALARM. They exist only while tasks are expected.
  task_alarm_count = var.app_desired_count > 0 ? 1 : 0

  target_group_dimensions = {
    TargetGroup  = aws_lb_target_group.app.arn_suffix
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

# ---- ALB targets ----

# HealthyHostCount has no data points while no target is registered, so missing
# data counts as breaching here: it is what a full outage can look like.
resource "aws_cloudwatch_metric_alarm" "service_down" {
  count = local.task_alarm_count

  alarm_name        = "${local.name}-service-down"
  alarm_description = "서비스 전체 중단: 정상 대상이 1 미만이다."

  namespace   = "AWS/ApplicationELB"
  metric_name = "HealthyHostCount"
  dimensions  = local.target_group_dimensions
  statistic   = "Minimum"

  comparison_operator = "LessThanThreshold"
  threshold           = 1
  period              = 60
  evaluation_periods  = 3
  treat_missing_data  = "breaching"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "tasks_below_desired" {
  count = local.task_alarm_count

  alarm_name        = "${local.name}-tasks-below-desired"
  alarm_description = "태스크 부족: 정상 대상이 app_desired_count보다 적다."

  namespace   = "AWS/ApplicationELB"
  metric_name = "HealthyHostCount"
  dimensions  = local.target_group_dimensions
  statistic   = "Minimum"

  comparison_operator = "LessThanThreshold"
  threshold           = var.app_desired_count
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "breaching"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

# ignore keeps the current state while data is missing. notBreaching would send
# an OK mail when the last unhealthy target is deregistered during an outage.
resource "aws_cloudwatch_metric_alarm" "unhealthy_targets" {
  count = local.task_alarm_count

  alarm_name        = "${local.name}-unhealthy-targets"
  alarm_description = "대상 비정상: 비정상 대상이 1 이상이다."

  namespace   = "AWS/ApplicationELB"
  metric_name = "UnHealthyHostCount"
  dimensions  = local.target_group_dimensions
  statistic   = "Maximum"

  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "ignore"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

# ---- 5xx ----

resource "aws_cloudwatch_metric_alarm" "target_5xx" {
  alarm_name        = "${local.name}-target-5xx"
  alarm_description = "앱 5xx: 5분 합계가 10 이상이다."

  namespace   = "AWS/ApplicationELB"
  metric_name = "HTTPCode_Target_5XX_Count"
  dimensions  = local.target_group_dimensions
  statistic   = "Sum"

  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 10
  period              = 300
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "elb_5xx" {
  alarm_name        = "${local.name}-elb-5xx"
  alarm_description = "ALB 5xx: 5분 합계가 5 이상이다."

  namespace   = "AWS/ApplicationELB"
  metric_name = "HTTPCode_ELB_5XX_Count"
  dimensions  = { LoadBalancer = aws_lb.main.arn_suffix }
  statistic   = "Sum"

  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 5
  period              = 300
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

# ---- ECS ----

# Works without Container Insights: with 2 running tasks the service metric
# showed SampleCount 2 per minute, and with no running task it has no data.
resource "aws_cloudwatch_metric_alarm" "no_running_tasks" {
  count = local.task_alarm_count

  alarm_name        = "${local.name}-no-running-tasks"
  alarm_description = "실행 태스크 0: ECS 서비스 지표가 들어오지 않는다."

  namespace   = "AWS/ECS"
  metric_name = "CPUUtilization"
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.app.name
  }
  statistic = "SampleCount"

  comparison_operator = "LessThanThreshold"
  threshold           = 1
  period              = 60
  evaluation_periods  = 3
  treat_missing_data  = "breaching"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

# ---- RDS ----

# Missing RDS data stays missing: the alarm moves to INSUFFICIENT_DATA, which
# sends no mail, and it sends no false OK while the instance restarts.
resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name        = "${local.name}-rds-free-storage"
  alarm_description = "RDS 저장 공간: 남은 공간이 4 GiB 미만이다."

  namespace   = "AWS/RDS"
  metric_name = "FreeStorageSpace"
  dimensions  = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  statistic   = "Minimum"

  comparison_operator = "LessThanThreshold"
  threshold           = 4 * 1024 * 1024 * 1024
  period              = 300
  evaluation_periods  = 1
  treat_missing_data  = "missing"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name        = "${local.name}-rds-cpu"
  alarm_description = "RDS CPU: 평균이 80%를 넘는다."

  namespace   = "AWS/RDS"
  metric_name = "CPUUtilization"
  dimensions  = { DBInstanceIdentifier = aws_db_instance.main.identifier }
  statistic   = "Average"

  comparison_operator = "GreaterThanThreshold"
  threshold           = 80
  period              = 300
  evaluation_periods  = 3
  treat_missing_data  = "missing"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
}
