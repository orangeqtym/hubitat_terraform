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
    "hubitat",
    "weather", 
    "govee",
    "database",
    "dashboard"
  ]
}

variable "github_token" {
  type    = string
  description = "create a new token with repo, admin:org permissions"
}

variable "service_port" {
  default     = 8000
  description = "Port for each service to run on inside containers"
  type        = number
}

variable "base_port" {
  default     = 8000
  description = "Base port for external service access (incremented for each service)"
  type        = number
}

variable "docker_subnet" {
  default     = "172.20.0.0/16"
  description = "Docker network subnet"
  type        = string
}

variable "docker_gateway" {
  default     = "172.20.0.1"
  description = "Docker network gateway"
  type        = string
}