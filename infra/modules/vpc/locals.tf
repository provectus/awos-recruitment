locals {
  private_subnet_newbits = var.env == "prod" ? 6 : 8
}
