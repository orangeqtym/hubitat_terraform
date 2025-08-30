# IoT System Deployment Guide

## Overview

This deployment guide covers the complete IoT infrastructure system with Docker containers managed by Terraform. The system includes five core services plus Redis for inter-service communication.

## Architecture Summary

### Services
- **Hubitat Service** (Port 8000): Smart hub device control and automation
- **Weather Service** (Port 8001): OpenWeatherMap API integration with caching  
- **Govee Service** (Port 8002): Govee sensor data collection and monitoring
- **Database Service** (Port 8003): SQLite-based sensor data storage with Redis auto-storage
- **Dashboard Service** (Port 8004): Real-time system health monitoring and web UI
- **Redis** (Port 6379): Message broker for pub/sub communication

### Key Features
- **Health Monitoring**: All services include comprehensive health checks
- **Resource Management**: Memory and CPU limits configured per service
- **Persistent Storage**: Dedicated volumes for Redis, database, and logs
- **Auto-Recovery**: Services restart automatically on failure
- **Centralized Logging**: JSON logs with rotation (10MB max, 3 files)
- **Inter-Service Communication**: Redis pub/sub for real-time data flow

## Prerequisites

1. **Docker**: Ensure Docker is installed and running
2. **Terraform**: Version 1.0+ with Docker provider
3. **Environment Variables**: Create single consolidated `.env` file
4. **Network Access**: Ensure ports 8000-8004 and 6379 are available

## Environment Setup

### Single Environment Configuration

Create a consolidated `.env` file in the project root:

```bash
# Copy template and customize
cp .env.template .env
# Edit with your actual values
```

#### .env (consolidated configuration)
```bash
# Redis Configuration (shared by all services)
REDIS_HOST=redis
REDIS_PORT=6379

# Hubitat Hub Configuration
HUBITAT_IP=192.168.86.25
HUBITAT_ACCESS_TOKEN=your_hubitat_access_token
HUBITAT_APP_ID=25

# Weather Service Configuration
OPENWEATHERMAP_API_KEY=your_openweather_api_key
WEATHER_LAT=40.04478164516005
WEATHER_LON=-75.48836741922985
WEATHER_LOCATION=Pennsylvania,US

# Govee Sensor Configuration
GOVEE_API_KEY=your_govee_api_key
GOVEE_SKU=H5179
GOVEE_DEVICE=your_govee_device_id

# Database Configuration
DATABASE_PATH=/app/data/sensor_data.db

# Dashboard Configuration
DASHBOARD_REFRESH_INTERVAL=30
```

**Benefits of Single `.env` File:**
- ✅ **No duplication** - Redis settings shared across all services
- ✅ **Single source of truth** - All configuration in one place
- ✅ **Easier deployment** - Only one file to manage
- ✅ **Consistent environment** - Same settings for all services

## Deployment Steps

### 1. Initialize Terraform

```bash
cd terraform/
terraform init
```

### 2. Configure Variables

Create `terraform.tfvars`:
```hcl
github_token = "your_github_token_here"
docker_subnet = "172.20.0.0/16"
docker_gateway = "172.20.0.1"
```

### 3. Plan Deployment

```bash
terraform plan
```

This will:
- Build Docker images for all services
- Show planned container and network configuration
- Validate all resources

### 4. Deploy Infrastructure

```bash
terraform apply
```

This will:
- Create Docker network (hubitat-services)
- Create persistent volumes (redis-data, database-data, service-logs)
- Build all service images
- Start Redis container
- Start all service containers
- Configure health checks and monitoring

### 5. Verify Deployment

#### Check Container Status
```bash
docker ps
```

#### Check Service Health
```bash
# Individual service health
curl http://localhost:8000/health  # Hubitat
curl http://localhost:8001/health  # Weather
curl http://localhost:8002/health  # Govee
curl http://localhost:8003/health  # Database
curl http://localhost:8004/health  # Dashboard

# System-wide health via dashboard
curl http://localhost:8004/system
```

#### Access Dashboard
Open browser to: http://localhost:8004

## Service URLs

After successful deployment:

- **Dashboard UI**: http://localhost:8004
- **Hubitat Service**: http://localhost:8000
- **Weather Service**: http://localhost:8001  
- **Govee Service**: http://localhost:8002
- **Database Service**: http://localhost:8003
- **Redis**: localhost:6379

## Monitoring and Logs

### Container Logs
```bash
# View service logs
docker logs hubitat-service
docker logs weather-service
docker logs govee-service
docker logs database-service
docker logs dashboard-service
docker logs redis

# Follow logs in real-time
docker logs -f dashboard-service
```

### Health Monitoring

The dashboard provides:
- Real-time service status
- Response time metrics
- System uptime percentage
- Individual service details
- Auto-refresh every 30 seconds

### Redis Monitoring
```bash
# Connect to Redis CLI
docker exec -it redis redis-cli

# Monitor Redis activity
docker exec -it redis redis-cli monitor

# Check Redis info
docker exec -it redis redis-cli info
```

## Data Flow

1. **Sensor Data Collection**: Govee and Hubitat services collect device data
2. **Weather Integration**: Weather service fetches external data every 15 minutes
3. **Redis Pub/Sub**: All services publish data to Redis channels
4. **Automatic Storage**: Database service subscribes to sensor-data channel and stores automatically
5. **Health Monitoring**: Dashboard service monitors all services and publishes system health
6. **Real-time Updates**: Dashboard UI shows live system status

## Troubleshooting

### Common Issues

#### Service Not Starting
```bash
# Check container status
docker ps -a

# Check service logs
docker logs <service-name>

# Restart specific service
docker restart <service-name>
```

#### Network Connectivity Issues
```bash
# Check Docker network
docker network ls
docker network inspect hubitat-services

# Test Redis connectivity
docker exec -it redis redis-cli ping
```

#### Volume/Data Issues
```bash
# Check volumes
docker volume ls
docker volume inspect redis-data database-data service-logs

# Check database file
docker exec -it database-service ls -la /app/data/
```

### Recovery Procedures

#### Full System Restart
```bash
# Stop all containers
docker stop $(docker ps -q)

# Restart infrastructure
terraform apply
```

#### Individual Service Recovery  
```bash
# Rebuild and restart single service
terraform apply -target=docker_container.service[\"service-name\"]
```

#### Data Recovery
- Database: SQLite file persisted in database-data volume
- Redis: AOF persistence enabled, data in redis-data volume
- Logs: Centralized in service-logs volume

## Performance Optimization

### Resource Limits
- **Database Service**: 512MB RAM, 1GB swap (higher for data processing)
- **Dashboard Service**: 1024 CPU shares (higher for monitoring)
- **Other Services**: 256MB RAM, 512 CPU shares
- **Redis**: 128MB max memory with LRU eviction

### Caching Strategy
- **Weather**: 15-minute cache for API data
- **Govee**: 2-minute cache for sensor readings
- **Dashboard**: 30-second cache for health data
- **Redis**: LRU eviction when memory limit reached

## Security Considerations

- All services run in isolated Docker network
- No external access to Redis (localhost only via port forwarding)
- Environment variables for sensitive data
- No hardcoded credentials in code
- Health checks use internal service communication
- Log rotation prevents disk space issues

## Updates and Maintenance

### Updating Services
```bash
# Rebuild images after code changes
terraform plan
terraform apply
```

### Scaling Considerations
- Current setup: Single instance per service
- For scaling: Modify instance_names variable and port mappings
- Add load balancer configuration as needed
- Consider Redis Cluster for high availability

## 🚀 GitHub Actions CI/CD Pipeline

The system includes a comprehensive automated deployment pipeline using GitHub Actions with self-hosted runners.

### 🔧 Self-Hosted Runner Setup

#### Quick Setup
Run the setup script on your server:
```bash
cd /path/to/hubitat_terraform
chmod +x scripts/setup-github-runner.sh
sudo ./scripts/setup-github-runner.sh
```

#### Manual GitHub Configuration
1. Go to: `https://github.com/YOUR_USERNAME/hubitat_terraform/settings/actions/runners`
2. Click "New self-hosted runner" → "Linux"
3. Run configuration:
   ```bash
   cd /opt/actions-runner
   sudo -u actions ./config.sh --url https://github.com/YOUR_USERNAME/hubitat_terraform --token YOUR_TOKEN
   ```
4. Install and start service:
   ```bash
   sudo ./svc.sh install actions
   sudo ./svc.sh start
   ```

### 🔄 Automated Deployment Process

#### Workflow Triggers
- **Push to `main`**: Full deployment with health checks
- **Push to `initial-changes`**: Full deployment with health checks  
- **Pull Request**: Test builds only (no deployment)

#### Deployment Steps
1. **🛑 Stop existing services** - Graceful container shutdown
2. **🔨 Build updated images** - Fresh builds of all 5 services
3. **🌐 Setup networking** - Docker networks and Redis message broker
4. **🚀 Start all services** - Launch containers in correct order
5. **🏥 Health checks** - Test all endpoints and connectivity
6. **📊 Data validation** - Verify sensor data collection
7. **🧹 Cleanup** - Remove old images and containers

### 📊 Deployment Verification

After successful deployment:

#### 🎯 Service Endpoints
- **Main Dashboard**: http://localhost:8004
- **Interactive Charts**: http://localhost:8004/charts  
- **Hubitat Control**: http://localhost:8000
- **Weather Data**: http://localhost:8001
- **Govee Sensors**: http://localhost:8002
- **Database API**: http://localhost:8003

#### 🔍 Health Monitoring
- Container status verification
- HTTP endpoint response checks
- Redis connectivity testing
- Database storage validation
- Sensor data flow verification

### 🚨 CI/CD Troubleshooting

#### Runner Issues
```bash
# Check runner service status
sudo systemctl status actions.runner.*

# View runner logs
sudo journalctl -u actions.runner.* -f

# Restart runner
sudo /opt/actions-runner/svc.sh stop
sudo /opt/actions-runner/svc.sh start
```

#### Deployment Failures
```bash
# Check GitHub Actions logs in repository
# Manual fallback deployment:
docker stop $(docker ps -q)
docker system prune -f
./scripts/manual-deploy.sh
```

### 🔒 Security & Best Practices

- Runner service runs as dedicated `actions` user
- Environment files never committed to repository
- Deployment uses isolated Docker networks
- Health checks ensure service readiness before marking deployment complete
- Automatic cleanup prevents disk space issues

### 🎉 Benefits of CI/CD Pipeline

- **Zero-downtime deployments** with health verification
- **Automatic rollback** if health checks fail
- **Consistent environment** across all deployments
- **Real-time monitoring** of deployment status
- **Complete audit trail** in GitHub Actions logs
- **Sensor data preservation** during updates

**Your IoT infrastructure now has enterprise-grade continuous deployment!** 🚀

This completes the comprehensive IoT infrastructure deployment with automated CI/CD, monitoring, persistence, and management.