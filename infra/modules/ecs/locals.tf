locals {
  task_family  = coalesce(var.task_family, "${var.ecs_cluster_name}-tasks")
  service_name = coalesce(var.service_name, "${var.ecs_cluster_name}-service")
}
