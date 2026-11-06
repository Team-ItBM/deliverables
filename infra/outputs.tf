# Values for GitHub repository variables (README bootstrap step 5).

output "github_deploy_role_arn" {
  description = "Repository variable AWS_DEPLOY_ROLE_ARN"
  value       = aws_iam_role.github_deploy.arn
}

output "ecr_repository" {
  description = "Repository variable ECR_REPOSITORY"
  value       = aws_ecr_repository.app.name
}

output "ecs_cluster" {
  description = "Repository variable ECS_CLUSTER"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service" {
  description = "Repository variable ECS_SERVICE"
  value       = aws_ecs_service.app.name
}

output "ecs_task_family" {
  description = "Repository variable ECS_TASK_FAMILY"
  value       = aws_ecs_task_definition.app.family
}

output "ecs_container_name" {
  description = "Repository variable ECS_CONTAINER_NAME"
  value       = local.container_name
}

output "spa_bucket" {
  description = "Repository variable SPA_BUCKET"
  value       = aws_s3_bucket.spa.bucket
}

output "cloudfront_distribution_id" {
  description = "Repository variable CLOUDFRONT_DISTRIBUTION_ID"
  value       = aws_cloudfront_distribution.main.id
}

output "site_url" {
  value = "https://${var.domain_name}"
}

output "db_endpoint" {
  value = aws_db_instance.main.address
}

output "secret_names" {
  value = local.secret_names
}

output "alert_topic_arn" {
  description = "Alarm topic, for checking the subscription status (README 장애 알람)"
  value       = aws_sns_topic.alerts.arn
}

output "db_init_command" {
  value = local.db_init_command
}
