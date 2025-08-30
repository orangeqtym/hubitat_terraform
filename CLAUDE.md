# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Terraform-based infrastructure project that deploys Docker containers on a local server for IoT device management and weather data processing. The project uses a modular approach with separate Python FastAPI services for different functions (weather, database, govee, hubitat), with Redis for inter-service communication.

## Architecture

The project follows this structure:
- **terraform/**: Contains all Terraform configuration files for local Docker infrastructure
- **{service}/**: Python service directories (weather, database, govee, hubitat) each with main.py, requirements.txt, Dockerfile, and __init__.py
- **.github/workflows/**: GitHub Actions workflows for CI/CD to local server

### Key Infrastructure Components

- **Docker Containers**: FastAPI-based Python services running in containers
- **Redis**: Message broker for pub/sub communication between services
- **Docker Networks**: Custom bridge network for service communication
- **GitHub Actions**: CI/CD pipeline with self-hosted runner on local server
- **Docker Volumes**: Persistent storage for Redis data and service logs

### Terraform Module Structure

- `providers.tf`: Docker and GitHub providers configuration
- `variables.tf`: Project variables including service ports, Docker networking, instance_names array
- `docker.tf`: Docker container resources with dynamic creation based on instance_names
- `networking.tf`: Docker networks and volumes setup
- `messaging.tf`: Redis container for pub/sub messaging
- `main.tf`: Orchestration file (minimal, used for additional resources)

## Common Commands

### Terraform Operations
```bash
# Navigate to terraform directory
cd terraform/

# Initialize Terraform
terraform init

# Plan changes (will build Docker images)
terraform plan

# Apply changes (deploys containers)
terraform apply

# Destroy infrastructure
terraform destroy

# View running containers
docker ps
```

### Required Variables
Set these variables in `terraform.tfvars` or as environment variables:
- `github_token`: GitHub token with repo and admin:org permissions
- `service_port`: Port for services inside containers (default: 8000)
- `base_port`: Base port for external access (default: 8000)
- `docker_subnet`: Docker network subnet (default: 172.20.0.0/16)

### Service Development
Each service directory (weather/, database/, etc.) contains:
- `main.py`: FastAPI application with health checks and Redis pub/sub
- `requirements.txt`: Python dependencies (FastAPI, uvicorn, redis, requests)
- `Dockerfile`: Container build configuration
- Services expose `/health` endpoint and have service-specific endpoints

### Local Server Deployment
Services are deployed via GitHub Actions to a self-hosted runner:
1. Push to main branch triggers deployment
2. Self-hosted runner builds Docker images via Terraform
3. Terraform manages container lifecycle
4. Health checks verify service deployment
5. Services accessible on base_port + service_index

### Service Communication
- Services communicate via Redis pub/sub channels
- Each service publishes processed data to Redis channels
- Services subscribe to relevant channels for inter-service messaging
- Direct HTTP communication also available via Docker network

## Service Endpoints

### Weather Service (port 8000)
- `GET /health` - Health check
- `POST /process` - Process weather data
- `GET /` - Service info

### Database Service (port 8001)  
- `GET /health` - Health check
- `POST /store` - Store data
- `GET /` - Service info

### Self-Hosted Runner Setup
To set up the GitHub Actions runner on your server:
1. Go to repository Settings > Actions > Runners
2. Click "New self-hosted runner" 
3. Follow instructions to install runner on your server
4. Ensure Docker and Terraform are installed on the server
5. Runner will automatically pick up deployment jobs

## Current Implementation Status
- Core infrastructure: Docker containers, Redis messaging, networking
- Active services: weather, database (govee, hubitat available but may need activation in instance_names)
- GitHub Actions integration for automated deployments to local server
- Health monitoring and service discovery configured