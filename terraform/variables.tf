variable "project_id" {
  default     = "qhubitat"
  description = "Your Google Cloud project ID"
  type        = string
}

variable "GCP_CLOUD_PROJECT_NUMBER" {
  description = "Your Google Cloud project #"
  type        = number
  default     = 1044605306561
}

variable "region" {
  default     = "northamerica-northeast1"
  description = "The region to deploy resources"
  type        = string
}

variable "python_version" {
  default     = "python312"
  description = "The region to deploy resources"
  type        = string
}

variable "python_memory" {
  default     = "256M"
  description = "How much memory each function gets"
  type        = string
}

variable "python_timeout" {
  default     = 60
  description = "How many seconds each function gets"
  type        = number
}

variable "instance_names" {
  type    = list(string)
  default = [
    "weather",
#    "govee",
#    "hubitat",
#    "database"
  ]
}

variable "github_token" {
  type    = string
  description = "create a new token with repo, admin:org permissions"
}