data "aws_route53_zone" "this" {
  name         = var.config.domain_name
  private_zone = var.config.private_zone == true ? var.config.private_zone : false
}

resource "aws_acm_certificate" "this" {
  domain_name               = var.config.domain_name
  subject_alternative_names = var.config.subject_alternative_names
  validation_method         = "DNS"

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "this" {
  zone_id = data.aws_route53_zone.this.zone_id

  for_each = {
    for validation_options in aws_acm_certificate.this.domain_validation_options : validation_options.domain_name => {
      name   = validation_options.resource_record_name
      record = validation_options.resource_record_value
      type   = validation_options.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
}

resource "aws_acm_certificate_validation" "this" {
  count                   = var.await_validation ? 1 : 0
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for record in aws_route53_record.this : record.fqdn]
}
