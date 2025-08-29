resource "docker_network" "services" {
  name   = "hubitat-services"
  driver = "bridge"
  
  ipam_config {
    subnet  = var.docker_subnet
    gateway = var.docker_gateway
  }
}

# Persistent volumes for data storage
resource "docker_volume" "redis_data" {
  name = "redis-data"
}

resource "docker_volume" "database_data" {
  name = "database-data"
}

# Shared log volume for centralized logging
resource "docker_volume" "service_logs" {
  name = "service-logs"
}

# Network outputs for reference
output "network_info" {
  description = "Docker network configuration"
  value = {
    name    = docker_network.services.name
    subnet  = var.docker_subnet
    gateway = var.docker_gateway
  }
}

output "volume_info" {
  description = "Docker volume configuration"
  value = {
    redis_data    = docker_volume.redis_data.name
    database_data = docker_volume.database_data.name
    service_logs  = docker_volume.service_logs.name
  }
}