import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import redis
import threading
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class DeviceCommand(BaseModel):
    command: str = Field(..., description="Command to send to device")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Optional command parameters")

class DeviceStatus(BaseModel):
    device_id: str
    name: str
    status: str
    last_updated: datetime
    capabilities: List[str]
    attributes: Dict[str, Any]

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    details: Dict[str, Any]

class HubitatAPI:
    def __init__(self):
        self.hubitat_ip = os.environ.get("HUBITAT_IP")
        self.access_token = os.environ.get("HUBITAT_ACCESS_TOKEN") 
        self.app_id = os.environ.get("HUBITAT_APP_ID")
        
        required_vars = ["HUBITAT_IP", "HUBITAT_ACCESS_TOKEN", "HUBITAT_APP_ID"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
        
        self.base_url = f"http://{self.hubitat_ip}/apps/api/{self.app_id}/devices"
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

    async def _make_request(self, method: str, endpoint: str, **kwargs):
        """Make an HTTP request to Hubitat API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, timeout=10, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Hubitat API error: {str(e)}")

    async def get_all_devices(self) -> List[Dict]:
        """Get all devices from Hubitat."""
        response = await self._make_request("GET", "/all")
        return response.json()

    async def get_device(self, device_id: str) -> Dict:
        """Get specific device info."""
        response = await self._make_request("GET", f"/{device_id}")
        return response.json()

    async def send_command(self, device_id: str, command: str, parameters: Optional[Dict] = None) -> Dict:
        """Send command to device."""
        endpoint = f"/{device_id}/{command}"
        if parameters:
            response = await self._make_request("POST", endpoint, json=parameters)
        else:
            response = await self._make_request("GET", endpoint)
        return response.json()

    async def check_hub_connectivity(self) -> Dict[str, Any]:
        """Check if Hubitat hub is reachable and responsive."""
        try:
            response = await self._make_request("GET", "/all")
            devices = response.json()
            return {
                "status": "online",
                "device_count": len(devices) if isinstance(devices, list) else 0,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "hub_ip": self.hubitat_ip
            }
        except Exception as e:
            return {
                "status": "offline",
                "error": str(e),
                "hub_ip": self.hubitat_ip
            }

# Global variables
hubitat_api: Optional[HubitatAPI] = None
redis_client: Optional[redis.Redis] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global hubitat_api, redis_client
    
    # Startup
    try:
        hubitat_api = HubitatAPI()
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )
        
        # Test connections
        redis_client.ping()
        await hubitat_api.check_hub_connectivity()
        
        # Start sensor data collection background task
        asyncio.create_task(sensor_data_collector())
        
        print("✅ Hubitat service started successfully with sensor data collection")
    except Exception as e:
        print(f"❌ Failed to start Hubitat service: {e}")
        raise
    
    yield
    
    # Shutdown
    if redis_client:
        redis_client.close()

app = FastAPI(
    title="Hubitat Service",
    version="1.0.0",
    description="Hubitat Hub integration service with health monitoring",
    lifespan=lifespan
)

async def get_hubitat_api() -> HubitatAPI:
    """Dependency to get HubitatAPI instance."""
    if hubitat_api is None:
        raise HTTPException(status_code=503, detail="Hubitat API not initialized")
    return hubitat_api

async def get_redis_client() -> redis.Redis:
    """Dependency to get Redis client."""
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis client not initialized")
    return redis_client

@app.get("/health", response_model=HealthCheck)
async def health_check(
    background_tasks: BackgroundTasks,
    hubitat: HubitatAPI = Depends(get_hubitat_api),
    redis: redis.Redis = Depends(get_redis_client)
):
    """Comprehensive health check including Hubitat hub and Redis connectivity."""
    health_details = {
        "service": "hubitat",
        "version": "1.0.0"
    }
    
    try:
        # Check Redis connection
        redis.ping()
        health_details["redis"] = "connected"
        
        # Check Hubitat hub connectivity
        hub_status = await hubitat.check_hub_connectivity()
        health_details["hubitat_hub"] = hub_status
        
        # Get basic device count
        devices = await hubitat.get_all_devices()
        health_details["device_count"] = len(devices) if isinstance(devices, list) else 0
        
        overall_status = "healthy" if hub_status.get("status") == "online" else "degraded"
        
        # Publish health status to Redis
        background_tasks.add_task(
            publish_health_status, 
            redis, 
            "hubitat", 
            overall_status, 
            health_details
        )
        
        return HealthCheck(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            details=health_details
        )
        
    except Exception as e:
        return HealthCheck(
            status="unhealthy",
            timestamp=datetime.now(timezone.utc),
            details={**health_details, "error": str(e)}
        )

@app.get("/devices", response_model=List[Dict])
async def get_devices(hubitat: HubitatAPI = Depends(get_hubitat_api)):
    """Get all Hubitat devices."""
    devices = await hubitat.get_all_devices()
    return devices

@app.get("/devices/{device_id}")
async def get_device(device_id: str, hubitat: HubitatAPI = Depends(get_hubitat_api)):
    """Get specific device information."""
    device = await hubitat.get_device(device_id)
    return device

@app.post("/devices/{device_id}/command")
async def send_device_command(
    device_id: str,
    command: DeviceCommand,
    background_tasks: BackgroundTasks,
    hubitat: HubitatAPI = Depends(get_hubitat_api),
    redis: redis.Redis = Depends(get_redis_client)
):
    """Send command to a specific device."""
    result = await hubitat.send_command(device_id, command.command, command.parameters)
    
    # Publish command result to Redis
    background_tasks.add_task(
        publish_device_command,
        redis,
        device_id,
        command.command,
        result
    )
    
    return {
        "device_id": device_id,
        "command": command.command,
        "parameters": command.parameters,
        "result": result,
        "timestamp": datetime.now(timezone.utc)
    }

@app.get("/diagnostics")
async def run_diagnostics(hubitat: HubitatAPI = Depends(get_hubitat_api)):
    """Run comprehensive diagnostics on Hubitat system."""
    diagnostics = {
        "timestamp": datetime.now(timezone.utc),
        "tests": {}
    }
    
    # Test hub connectivity
    hub_status = await hubitat.check_hub_connectivity()
    diagnostics["tests"]["hub_connectivity"] = hub_status
    
    # Test device enumeration
    try:
        devices = await hubitat.get_all_devices()
        diagnostics["tests"]["device_enumeration"] = {
            "status": "passed",
            "device_count": len(devices) if isinstance(devices, list) else 0
        }
    except Exception as e:
        diagnostics["tests"]["device_enumeration"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Test sample device query (if devices exist)
    try:
        devices = await hubitat.get_all_devices()
        if devices and len(devices) > 0:
            sample_device = devices[0]
            device_id = sample_device.get("id")
            if device_id:
                device_details = await hubitat.get_device(str(device_id))
                diagnostics["tests"]["sample_device_query"] = {
                    "status": "passed",
                    "device_id": device_id,
                    "device_name": sample_device.get("name", "unknown")
                }
        else:
            diagnostics["tests"]["sample_device_query"] = {
                "status": "skipped",
                "reason": "no_devices_found"
            }
    except Exception as e:
        diagnostics["tests"]["sample_device_query"] = {
            "status": "failed", 
            "error": str(e)
        }
    
    return diagnostics

@app.post("/sensors/publish")
async def publish_sensors_now(
    background_tasks: BackgroundTasks,
    hubitat: HubitatAPI = Depends(get_hubitat_api),
    redis: redis.Redis = Depends(get_redis_client)
):
    """Manually trigger sensor data collection and publishing."""
    try:
        devices = await hubitat.get_all_devices()
        background_tasks.add_task(publish_sensor_readings, redis, devices)
        
        sensor_count = sum(1 for device in devices 
                          if any(cap in ["TemperatureMeasurement", "RelativeHumidityMeasurement"] 
                                for cap in device.get("capabilities", [])))
        
        return {
            "status": "success",
            "message": "Sensor data publishing triggered",
            "total_devices": len(devices),
            "sensor_devices": sensor_count,
            "timestamp": datetime.now(timezone.utc)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish sensors: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Hubitat Integration Service",
        "version": "1.0.0",
        "description": "Hubitat Hub integration with comprehensive health monitoring and sensor data publishing",
        "endpoints": [
            "/health - Health check",
            "/devices - Get all devices", 
            "/devices/{id} - Get specific device",
            "/devices/{id}/command - Send device command",
            "/sensors/publish - Manually publish sensor data (POST)",
            "/diagnostics - Run system diagnostics"
        ],
        "timestamp": datetime.now(timezone.utc)
    }

def publish_sensor_readings(redis_conn: redis.Redis, devices: List[Dict]):
    """Publish sensor readings from Hubitat devices to Redis."""
    try:
        for device in devices:
            # Only publish devices with temperature/humidity sensors
            if any(cap in ["TemperatureMeasurement", "RelativeHumidityMeasurement"] 
                   for cap in device.get("capabilities", [])):
                
                # Extract sensor data
                attributes = device.get("attributes", {})
                temperature = attributes.get("temperature")
                humidity = attributes.get("humidity")
                battery = attributes.get("battery")
                
                # Convert values to proper types
                try:
                    temperature = float(temperature) if temperature else None
                    humidity = float(humidity) if humidity else None
                    battery = int(battery) if battery else None
                except (ValueError, TypeError):
                    continue  # Skip if conversion fails
                
                # Create sensor reading message
                message = {
                    "service": "hubitat",
                    "type": "sensor_reading",
                    "data": {
                        "status": "success",
                        "device_id": f"hubitat_{device['label'].replace(' ', '_').lower()}",
                        "device_name": device['label'],
                        "device_type": device['type'],
                        "room": device.get('room', 'Unknown'),
                        "temperature": temperature,
                        "humidity": humidity,
                        "battery_level": battery,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "raw_device_id": device['id']
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Publish to sensor-data channel (same as Govee)
                redis_conn.publish("sensor-data", json.dumps(message, default=str))
                logger.info(f"Published sensor data for {device['label']}: {temperature}°F, {humidity}%")
    
    except Exception as e:
        logger.error(f"Failed to publish sensor readings: {e}")

async def sensor_data_collector():
    """Background task to periodically collect and publish sensor data."""
    while True:
        try:
            if redis_client:
                # Get current device data
                devices_data = await hubitat_api.get_all_devices()
                if devices_data:
                    # Publish sensor readings
                    publish_sensor_readings(redis_client, devices_data)
                
                # Wait 5 minutes before next collection
                await asyncio.sleep(300)  # 300 seconds = 5 minutes
            else:
                await asyncio.sleep(60)  # Wait 1 minute if no Redis connection
                
        except Exception as e:
            logger.error(f"Sensor data collector error: {e}")
            await asyncio.sleep(60)

def publish_health_status(redis_conn: redis.Redis, service: str, status: str, details: Dict):
    """Publish health status to Redis."""
    try:
        message = {
            "service": service,
            "status": status,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        redis_conn.publish("health-updates", json.dumps(message, default=str))
    except Exception as e:
        print(f"Failed to publish health status: {e}")

def publish_device_command(redis_conn: redis.Redis, device_id: str, command: str, result: Dict):
    """Publish device command result to Redis."""
    try:
        message = {
            "service": "hubitat",
            "device_id": device_id,
            "command": command,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        redis_conn.publish("device-commands", json.dumps(message, default=str))
    except Exception as e:
        print(f"Failed to publish device command: {e}")

def print_hubitat():
    """Legacy function for backwards compatibility."""
    print("Hubitat Service - FastAPI Integration Ready")

if __name__ == '__main__':
    print_hubitat()