variable "config" {
  description = "Certificate request details."
  type = object({
    domain_name               = string
    subject_alternative_names = list(string)
    private_zone              = bool
  })
}

variable "await_validation" {
  description = "Either to wait until AWS ACM certificate is moved to `Issued` state."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to the certificate."
  type        = map(string)
  default     = {}
}

