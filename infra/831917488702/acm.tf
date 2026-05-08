# # ---------------------------------------------------------------------------
# # ACM Certificate with DNS Validation via Route 53
# # ---------------------------------------------------------------------------
module "acm_certificates" {
  source   = "../modules/acm_certificate"
  for_each = local.acm_certificates
  config = {
    domain_name               = each.value["domain_name"]
    subject_alternative_names = each.value["subject_alternative_names"]
    private_zone              = each.value["private_zone"]
  }
  # setting to true will result in the wait time during the apply
  await_validation = true
  tags             = local.default_tags
}
