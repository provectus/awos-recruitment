output "task_definition_arn" {
  value = aws_ecs_task_definition.this.arn_without_revision
}

output "task_definition_revision" {
  value = aws_ecs_task_definition.this.revision
}

output "ecs_cluster_arn" {
  value = module.ecs[0].cluster_arn
}

output "ecs_cluster_name" {
  value       = var.ecs_cluster_name
  description = "The name of the ECS cluster."
}

output "ecs_task_log_group_name" {
  value = aws_cloudwatch_log_group.task_definition.name
}

output "ecs_container_name" {
  value = var.container_name
}

output "service_name" {
  value = local.service_name
}
