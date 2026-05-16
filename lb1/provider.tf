terraform {
  required_providers {
    bigip = {
      source  = "F5Networks/bigip"
      version = "~> 1.22"
    }
  }
}

provider "bigip" {
  address  = var.bigip_address
  username = var.bigip_username
  password = var.bigip_password
}

variable "bigip_address" {
  description = "BIG-IP management IP address"
  type        = string
}

variable "bigip_username" {
  description = "BIG-IP admin username"
  type        = string
  default     = "admin"
}

variable "bigip_password" {
  description = "BIG-IP admin password"
  type        = string
  sensitive   = true
}
