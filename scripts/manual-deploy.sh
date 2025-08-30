#!/bin/bash

# Manual Deployment Script - Fallback for GitHub Actions
# This script manually deploys the IoT infrastructure without GitHub Actions

set -e

echo "🚀 Manual IoT Infrastructure Deployment"
echo "======================================"

# Change to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "📁 Working directory: $PROJECT_ROOT"

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running"
    exit 1
fi

echo "✅ Docker is available"

# Check environment files
echo "🔧 Checking environment files..."
if [ -f ".env" ]; then
    echo "✅ .env exists (consolidated configuration)"
else
    echo "❌ Missing environment file: .env"
    echo "   Please create .env file with all required environment variables"
    echo "   You can copy from .env.template and fill in your values"
    exit 1
fi

# Stop existing services
echo "🛑 Stopping existing services..."
docker stop hubitat weather govee database dashboard redis 2>/dev/null || true
docker rm hubitat weather govee database dashboard redis 2>/dev/null || true

# Build all Docker images
echo "🔨 Building Docker images..."
services=("hubitat" "weather" "govee" "database" "dashboard")

for service in "${services[@]}"; do
    echo "Building $service..."
    docker build -t "hubitat_terraform_$service:latest" "$service/"
done

echo "✅ All images built successfully"

# Create Docker network
echo "🌐 Setting up Docker network..."
docker network create hubitat-services --subnet=172.20.0.0/16 2>/dev/null || echo "Network already exists"

# Start Redis
echo "🔴 Starting Redis message broker..."
docker run -d --name redis \
    --network hubitat-services \
    --ip 172.20.0.10 \
    -p 6379:6379 \
    --restart unless-stopped \
    redis:7-alpine redis-server --appendonly yes --bind 0.0.0.0 --protected-mode no

echo "✅ Redis started"

# Start all services
echo "🚀 Starting IoT services..."

# Hubitat Service
docker run -d --name hubitat \
    --network hubitat-services \
    --env-file .env \
    -p 8000:8000 \
    --restart unless-stopped \
    hubitat_terraform_hubitat:latest

# Weather Service
docker run -d --name weather \
    --network hubitat-services \
    --env-file .env \
    -p 8001:8000 \
    --restart unless-stopped \
    hubitat_terraform_weather:latest

# Govee Service  
docker run -d --name govee \
    --network hubitat-services \
    --env-file .env \
    -p 8002:8000 \
    --restart unless-stopped \
    hubitat_terraform_govee:latest

# Database Service
docker run -d --name database \
    --network hubitat-services \
    --env-file .env \
    -p 8003:8000 \
    --restart unless-stopped \
    hubitat_terraform_database:latest

# Dashboard Service
docker run -d --name dashboard \
    --network hubitat-services \
    --env-file .env \
    -p 8004:8000 \
    --restart unless-stopped \
    hubitat_terraform_dashboard:latest

echo "✅ All services started"

# Wait for services to initialize
echo "⏱️ Waiting for services to initialize..."
sleep 45

# Health checks
echo "🏥 Performing health checks..."

# Check Redis
if docker exec redis redis-cli ping | grep -q PONG; then
    echo "✅ Redis is healthy"
else
    echo "❌ Redis health check failed"
    exit 1
fi

# Check service containers
services_ports=("hubitat:8000" "weather:8001" "govee:8002" "database:8003" "dashboard:8004")

for service_port in "${services_ports[@]}"; do
    service=${service_port%%:*}
    port=${service_port##*:}
    
    if docker ps --filter "name=$service" --filter "status=running" | grep -q "$service"; then
        echo "✅ $service container is running"
        
        # Test HTTP endpoint
        if timeout 10 curl -f -s "http://localhost:$port/health" > /dev/null 2>&1 || \
           timeout 10 curl -f -s "http://localhost:$port/" > /dev/null 2>&1; then
            echo "✅ $service HTTP endpoint is responding"
        else
            echo "⚠️ $service HTTP endpoint not responding (may still be starting)"
        fi
    else
        echo "❌ $service container failed to start"
        docker logs "$service" --tail 20 || true
        exit 1
    fi
done

# Test sensor data collection
echo "📊 Testing sensor data collection..."
sleep 30

if curl -s http://localhost:8003/stats | grep -q '"total_readings"'; then
    readings=$(curl -s http://localhost:8003/stats | python3 -c "import sys,json; print(json.load(sys.stdin)['total_readings'])" 2>/dev/null || echo "0")
    sensors=$(curl -s http://localhost:8003/stats | python3 -c "import sys,json; print(json.load(sys.stdin)['unique_sensors'])" 2>/dev/null || echo "0") 
    echo "✅ Database contains $readings readings from $sensors sensors"
else
    echo "⚠️ Database statistics not available yet"
fi

# Display deployment summary
echo ""
echo "🎉 Manual deployment completed successfully!"
echo ""
echo "📍 Service Endpoints:"
echo "   • Main Dashboard: http://localhost:8004"
echo "   • Charts & Data:  http://localhost:8004/charts"
echo "   • Hubitat Hub:    http://localhost:8000"
echo "   • Weather API:    http://localhost:8001"
echo "   • Govee Sensors:  http://localhost:8002"
echo "   • Database API:   http://localhost:8003"
echo ""
echo "📊 System Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Cleanup
echo "🧹 Cleaning up old images..."
docker image prune -f
docker system prune -f --volumes=false

echo "✅ Deployment complete! Your IoT infrastructure is ready."