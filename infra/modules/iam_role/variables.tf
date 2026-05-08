variable "name" {
  description = "The name of the IAM role"
  type        = string
}

variable "assume_role_policy" {
  description = "Trust policy JSON document granting the role to be assumed"
  type        = string
}

variable "managed_policy_arns" {
  description = "List of AWS- or customer-managed policy ARNs to attach to the role"
  type        = list(string)
  default     = []
}

variable "inline_policies" {
  description = "Map of inline policy name to policy JSON document"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Map of tags to apply to the role"
  type        = map(string)
  default     = {}
}
