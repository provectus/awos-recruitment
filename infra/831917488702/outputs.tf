# output "ecr_repository_url" {
#   description = "URL of the ECR repository for the MCP server image"
#   value       = aws_ecr_repository.mcp.repository_url
# }

# output "alb_dns_name" {
#   description = "DNS name of the Application Load Balancer"
#   value       = aws_lb.main.dns_name
# }

# output "ecs_cluster_name" {
#   description = "Name of the ECS cluster"
#   value       = aws_ecs_cluster.main.name
# }

# output "ecs_service_name" {
#   description = "Name of the ECS service"
#   value       = aws_ecs_service.mcp.name
# }

# output "github_deploy_role_arn" {
#   description = "ARN of the IAM role GitHub Actions assumes via OIDC to deploy"
#   value       = aws_iam_role.github_deploy.arn
# }
