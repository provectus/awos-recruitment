variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "env" {
  description = "Deployment environment name"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC for ECS resources"
  type        = string
  default     = ""
}

variable "execution_role_arn" {
  description = "ARN of the ECS task execution IAM role"
  type        = string
}

variable "private_subnets" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
  default     = []
}

variable "aws_region" {
  description = "AWS region for ECS deployment"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the IAM role for ECS task permissions"
  type        = string
}

variable "tags" {
  description = "A map of key-value pairs to assign metadata to resources"
  type        = map(string)
}

variable "docker_image_task_definition" {
  description = "Docker image for the ECS task definition"
  type        = string
}

variable "container_name" {
  description = "Name of the container in the ECS task definition"
  type        = string
}

variable "ecs_service_enabled" {
  description = "Enable the ECS service for the task"
  type        = bool
  default     = false
}

variable "ecs_cluster_enabled" {
  description = "Enable creation of the ECS cluster"
  type        = bool
  default     = true
}

variable "task_command" {
  description = "Command to run the application in the container"
  type        = list(string)
  default     = null
}

variable "ecs_task_env_variables" {
  description = "A list of environment variables to pass to the ECS task"
  type        = list(any)
  default     = []
}

variable "ecs_task_cpu_limit" {
  description = "Maximum CPU units allocated for the ECS task"
  type        = number
  default     = 512
}

variable "ecs_task_memory_limit" {
  description = "Maximum memory (in MiB) allocated for the ECS task"
  type        = number
  default     = 1024
}

variable "ecs_task_container_port" {
  description = "Container port exposed by the ECS task"
  type        = number
  default     = 80
}

variable "ecs_task_host_port" {
  description = "Host port mapped to the container port"
  type        = number
  default     = 80
}

variable "ecs_security_group_id" {
  description = "List of security group IDs for ECS tasks"
  type        = list(string)
  default     = []
}

variable "desired_count" {
  description = "Desired number of ECS task instances"
  type        = number
  default     = 1
}

variable "task_family" {
  description = "Override for the ECS task definition family. Defaults to <cluster>-tasks if null."
  type        = string
  default     = null
}

variable "service_name" {
  description = "Override for the ECS service name. Defaults to <cluster>-service if null."
  type        = string
  default     = null
}

variable "secrets" {
  description = "List of container secrets pulled from SSM Parameter Store or Secrets Manager"
  type = list(object({
    name      = string
    valueFrom = string
  }))
  default = []
}

variable "target_group_arn" {
  description = "ALB target group ARN to attach the ECS service to. If null, no load balancer is configured."
  type        = string
  default     = null
}

variable "health_check_grace_period_seconds" {
  description = "Seconds to ignore failing load balancer health checks on newly launched tasks"
  type        = number
  default     = 0
}

variable "deployment_minimum_healthy_percent" {
  description = "Lower limit (% of desired_count) of running tasks during a deployment"
  type        = number
  default     = 100
}

variable "deployment_maximum_percent" {
  description = "Upper limit (% of desired_count) of running tasks during a deployment"
  type        = number
  default     = 200
}

variable "enable_deployment_circuit_breaker" {
  description = "Enable ECS deployment circuit breaker with rollback"
  type        = bool
  default     = false
}
