# Service port mapping for external access
locals {
  service_ports = {
    hubitat   = 8000
    weather   = 8001 
    govee     = 8002
    database  = 8003
    dashboard = 8004
  }
}

resource "docker_image" "service_image" {
  for_each = {for idx, val in var.instance_names : val => idx}
  name     = "${each.key}-service:latest"
  
  build {
    context    = "../${each.key}/"
    dockerfile = "Dockerfile"
    tag        = ["${each.key}-service:latest"]
    build_args = {
      SERVICE_NAME = each.key
      BUILD_DATE   = timestamp()
    }
  }
  
  triggers = {
    dir_sha1 = sha1(join("", [for f in fileset("../${each.key}", "**") : filesha1("../${each.key}/${f}")]))
  }
}

resource "docker_container" "service" {
  for_each = {for idx, val in var.instance_names : val => idx}
  name     = "${each.key}-service"
  image    = docker_image.service_image[each.key].image_id
  
  restart = "unless-stopped"
  
  ports {
    internal = var.service_port
    external = local.service_ports[each.key]
  }
  
  networks_advanced {
    name = docker_network.services.name
    aliases = [each.key]
  }
  
  # Environment variables with service-specific configuration
  env = [
    "SERVICE_NAME=${each.key}",
    "REDIS_HOST=redis",
    "REDIS_PORT=6379",
    "SERVICE_PORT=${var.service_port}",
    "LOG_LEVEL=INFO",
    "PYTHONUNBUFFERED=1",
    "TZ=America/Toronto"
  ]
  
  # Resource limits for better resource management
  memory = each.key == "database" ? 512 : 256
  memory_swap = each.key == "database" ? 1024 : 512
  
  # CPU limits (relative weight)
  cpu_shares = each.key == "dashboard" ? 1024 : 512
  
  depends_on = [docker_container.redis]
  
  # Enhanced health checks with service-specific configuration
  healthcheck {
    test = each.key == "dashboard" ? [
      "CMD-SHELL", 
      "curl -f http://localhost:${var.service_port}/health || exit 1"
    ] : [
      "CMD-SHELL", 
      "python -c \"import requests; requests.get('http://localhost:${var.service_port}/health', timeout=5).raise_for_status()\" || exit 1"
    ]
    interval    = "30s"
    timeout     = "15s"
    retries     = 3
    start_period = "60s"
  }
  
  # Logging configuration with rotation
  log_driver = "json-file"
  log_opts = {
    "max-size" = "10m"
    "max-file" = "3"
    "labels"   = "service=${each.key}"
  }
  
  # Labels for better container management and monitoring  
  labels {
    label = "com.iot.service"
    value = each.key
  }
  labels {
    label = "com.iot.type"
    value = "microservice"
  }
  
  # Volume mounts for persistent data (database service)
  dynamic "volumes" {
    for_each = each.key == "database" ? [1] : []
    content {
      volume_name    = docker_volume.database_data.name
      container_path = "/app/data"
    }
  }
  
  # Volume mounts for logs
  volumes {
    volume_name    = docker_volume.service_logs.name
    container_path = "/app/logs"
  }
}

# Output service information for easy access
output "service_urls" {
  description = "URLs for accessing each service"
  value = {
    for service, port in local.service_ports : 
    service => "http://localhost:${port}"
  }
}

output "service_health_urls" {
  description = "Health check URLs for each service"
  value = {
    for service, port in local.service_ports : 
    service => "http://localhost:${port}/health"
  }
}

output "dashboard_url" {
  description = "Main dashboard URL"
  value = "http://localhost:${local.service_ports["dashboard"]}"
}