resource "docker_image" "redis" {
  name = "redis:7-alpine"
}

resource "docker_container" "redis" {
  name  = "redis"
  image = docker_image.redis.image_id
  
  restart = "unless-stopped"
  
  ports {
    internal = 6379
    external = 6379
  }
  
  networks_advanced {
    name = docker_network.services.name
    aliases = ["redis", "message-broker"]
  }
  
  volumes {
    volume_name    = docker_volume.redis_data.name
    container_path = "/data"
  }
  
  # Resource limits for Redis
  memory      = 256
  memory_swap = 512
  cpu_shares  = 1024
  
  # Enhanced Redis configuration with monitoring and persistence
  command = [
    "redis-server",
    "--appendonly", "yes",
    "--bind", "0.0.0.0", 
    "--protected-mode", "no",
    "--maxmemory", "128mb",
    "--maxmemory-policy", "allkeys-lru",
    "--save", "300", "10",
    "--save", "60", "1000",
    "--loglevel", "notice",
    "--tcp-keepalive", "300",
    "--timeout", "0"
  ]
  
  # Enhanced health check with more comprehensive testing
  healthcheck {
    test = [
      "CMD-SHELL", 
      "redis-cli ping | grep PONG && redis-cli info replication | grep role:master"
    ]
    interval     = "15s"
    timeout      = "10s"
    retries      = 3
    start_period = "30s"
  }
  
  # Logging configuration
  log_driver = "json-file"
  log_opts = {
    "max-size" = "10m"
    "max-file" = "3"
    "labels"   = "service=redis"
  }
  
  # Labels for better container management
  labels {
    label = "com.iot.service"
    value = "redis"
  }
  labels {
    label = "com.iot.type"
    value = "message-broker"
  }
  
  # Environment variables
  env = [
    "TZ=America/Toronto"
  ]
}

# Output Redis connection information
output "redis_info" {
  description = "Redis connection information"
  value = {
    host     = "localhost"
    port     = 6379
    url      = "redis://localhost:6379"
    internal = "redis://redis:6379"
  }
}