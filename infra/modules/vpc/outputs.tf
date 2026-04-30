output "vpc_id" {
  value = module.vpc.vpc_id
}

output "default_security_group_id" {
  value = module.vpc.default_security_group_id
}

output "public_subnets" {
  value = module.vpc.public_subnets
}

output "private_subnets" {
  value = module.vpc.private_subnets
}

output "intra_subnets" {
  value = var.create_intra_subnets == true ? module.vpc.intra_subnets : null
}

output "database_subnets" {
  value = var.create_database_subnets == true ? module.vpc.database_subnets : null
}

output "general_security_group_id" {
  value = aws_security_group.this.id
}

output "private_route_table_ids" {
  value = module.vpc.private_route_table_ids
}

output "public_route_table_ids" {
  value = module.vpc.public_route_table_ids
}

output "database_subnets_cidr_blocks" {
  value = module.vpc.database_subnets_cidr_blocks
}
