# # ---------------------------------------------------------------------------
# # Route 53 DNS Record: A record (alias) pointing to the ALB
# # ---------------------------------------------------------------------------

resource "aws_route53_zone" "subdomain" {
  name = local.main_domain_name

  tags = local.default_tags
}

resource "aws_route53_record" "app" {
  zone_id = aws_route53_zone.subdomain.zone_id
  name    = local.sub_domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
