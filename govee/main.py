import os
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager

import redis
import threading
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from dotenv import load_dotenv
from cachetools import TTLCache
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for sensor data (2-minute TTL for sensors)
sensor_cache = TTLCache(maxsize=50, ttl=120)

# Pydantic models
class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    details: Dict[str, Any]

class GoveeAPI:
    def __init__(self):
        self.api_key = os.environ.get("GOVEE_API_KEY")
        self.sku = os.environ.get("GOVEE_SKU")
        self.device_id = os.environ.get("GOVEE_DEVICE")
        self.base_url = "https://openapi.api.govee.com/router/api/v1/device/state"
        
        required_vars = ["GOVEE_API_KEY", "GOVEE_SKU", "GOVEE_DEVICE"]
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        if missing_vars:
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")

    async def get_device_state(self, use_cache: bool = True) -> Dict:
        """Get current device sensor readings with caching and validation."""
        cache_key = f"govee_{self.device_id}_{self.sku}"
        
        # Check cache first
        if use_cache and cache_key in sensor_cache:
            logger.info("Returning cached Govee sensor data")
            return sensor_cache[cache_key]
        
        request_id = str(uuid.uuid4())
        payload = {
            "requestId": request_id,
            "payload": {
                "sku": self.sku,
                "device": self.device_id
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Govee-API-Key": self.api_key
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Parse sensor data from response
            sensor_result = await self._parse_sensor_data(data, request_id)
            
            # Cache the result if successful
            if sensor_result.get("status") == "success":
                sensor_cache[cache_key] = sensor_result
            
            return sensor_result
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Govee API HTTP error: {e}"
            if e.response is not None:
                error_msg += f" - {e.response.text[:200]}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error accessing Govee API: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        except Exception as e:
            error_msg = f"Unexpected error in Govee API: {e}"
            logger.exception(error_msg)
            return {"status": "error", "message": error_msg}

    async def _parse_sensor_data(self, data: Dict, request_id: str) -> Dict:
        """Parse sensor data from Govee API response with comprehensive validation."""
        try:
            payload_data = data.get('payload', {})
            capabilities = payload_data.get('capabilities', [])
            
            if not capabilities:
                return {
                    "status": "error",
                    "message": "No capabilities found in device response",
                    "device_id": self.device_id,
                    "request_id": request_id
                }
            
            temperature = None
            humidity = None
            battery_level = None
            
            # Parse capabilities array - structure can vary by device
            for i, capability in enumerate(capabilities):
                if not isinstance(capability, dict):
                    continue
                    
                state = capability.get('state', {})
                if not isinstance(state, dict):
                    continue
                
                value = state.get('value')
                instance = capability.get('instance', '')
                
                # Temperature detection
                if ('temperature' in instance.lower() or 
                    (i == 1 and isinstance(value, (int, float)))):
                    if isinstance(value, (int, float)) and -100 <= value <= 150:
                        temperature = float(value)
                
                # Humidity detection
                elif ('humidity' in instance.lower() or 
                      (i == 2 and value is not None)):
                    if isinstance(value, dict) and 'currentHumidity' in value:
                        humidity_val = value.get('currentHumidity')
                        if isinstance(humidity_val, (int, float)) and 0 <= humidity_val <= 100:
                            humidity = float(humidity_val)
                    elif isinstance(value, (int, float)) and 0 <= value <= 100:
                        humidity = float(value)
                
                # Battery level detection
                elif 'battery' in instance.lower():
                    if isinstance(value, (int, float)) and 0 <= value <= 100:
                        battery_level = int(value)
            
            # Validate that we got at least one useful reading
            if temperature is None and humidity is None:
                return {
                    "status": "error",
                    "message": "Could not extract temperature or humidity from device response",
                    "device_id": self.device_id,
                    "request_id": request_id
                }
            
            sensor_result = {
                "status": "success",
                "temperature": temperature,
                "humidity": humidity,
                "battery_level": battery_level,
                "device_id": self.device_id,
                "device_sku": self.sku,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "capabilities_count": len(capabilities)
            }
            
            logger.info(f"Successfully parsed Govee sensor data: {temperature}°F, {humidity}%")
            return sensor_result
            
        except Exception as e:
            logger.exception(f"Error parsing Govee sensor data: {e}")
            return {
                "status": "error",
                "message": f"Failed to parse sensor data: {str(e)}",
                "device_id": self.device_id,
                "request_id": request_id
            }

    async def check_device_connectivity(self) -> Dict[str, Any]:
        """Test Govee device connectivity and API access."""
        try:
            start_time = time.time()
            sensor_data = await self.get_device_state(use_cache=False)
            response_time = (time.time() - start_time) * 1000
            
            if sensor_data.get("status") == "success":
                return {
                    "status": "online",
                    "api_key_valid": True,
                    "device_responsive": True,
                    "response_time_ms": response_time,
                    "device_id": self.device_id,
                    "device_sku": self.sku,
                    "has_temperature": sensor_data.get("temperature") is not None,
                    "has_humidity": sensor_data.get("humidity") is not None,
                    "battery_level": sensor_data.get("battery_level")
                }
            else:
                return {
                    "status": "error",
                    "api_key_valid": True,
                    "device_responsive": False,
                    "error": sensor_data.get("message", "Unknown error"),
                    "device_id": self.device_id,
                    "device_sku": self.sku
                }
                
        except Exception as e:
            return {
                "status": "error",
                "api_key_valid": False,
                "device_responsive": False,
                "error": str(e),
                "device_id": self.device_id,
                "device_sku": self.sku
            }

# Global variables
govee_api: Optional[GoveeAPI] = None
redis_client: Optional[redis.Redis] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global govee_api, redis_client
    
    # Startup
    try:
        govee_api = GoveeAPI()
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )
        
        # Test connections
        redis_client.ping()
        connectivity_test = await govee_api.check_device_connectivity()
        
        if connectivity_test.get("status") != "online":
            logger.warning(f"Govee device connectivity issue: {connectivity_test}")
        
        print("✅ Govee service started successfully")
    except Exception as e:
        print(f"❌ Failed to start Govee service: {e}")
        raise
    
    yield
    
    # Shutdown
    if redis_client:
        redis_client.close()

app = FastAPI(
    title="Govee Service",
    version="1.0.0",
    description="Govee smart sensor integration service with comprehensive monitoring",
    lifespan=lifespan
)

async def get_govee_api() -> GoveeAPI:
    if govee_api is None:
        raise HTTPException(status_code=503, detail="Govee API not initialized")
    return govee_api

async def get_redis_client() -> redis.Redis:
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis client not initialized")
    return redis_client

@app.get("/health", response_model=HealthCheck)
async def health_check(
    background_tasks: BackgroundTasks,
    govee: GoveeAPI = Depends(get_govee_api),
    redis: redis.Redis = Depends(get_redis_client)
):
    health_details = {"service": "govee", "version": "1.0.0"}
    
    try:
        # Check Redis connection
        redis.ping()
        health_details["redis"] = "connected"
        
        # Check Govee device connectivity
        device_status = await govee.check_device_connectivity()
        health_details["govee_device"] = device_status
        
        # Check cache status
        health_details["cache_size"] = len(sensor_cache)
        
        overall_status = "healthy" if device_status.get("status") == "online" else "degraded"
        
        # Publish health status to Redis
        background_tasks.add_task(publish_health_status, redis, "govee", overall_status, health_details)
        
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

@app.get("/sensors/current")
async def get_current_sensor_data(
    background_tasks: BackgroundTasks,
    use_cache: bool = True,
    govee: GoveeAPI = Depends(get_govee_api),
    redis: redis.Redis = Depends(get_redis_client)
):
    sensor_data = await govee.get_device_state(use_cache=use_cache)
    
    if sensor_data.get("status") == "success":
        # Publish sensor data to Redis for other services
        background_tasks.add_task(publish_sensor_data, redis, sensor_data)
    
    return sensor_data

@app.get("/devices")
async def get_device_info(govee: GoveeAPI = Depends(get_govee_api)):
    return {
        "device_id": govee.device_id,
        "device_sku": govee.sku,
        "api_endpoint": govee.base_url,
        "status": "configured"
    }

@app.get("/diagnostics")
async def run_diagnostics(govee: GoveeAPI = Depends(get_govee_api)):
    diagnostics = {"timestamp": datetime.now(timezone.utc), "tests": {}}
    
    # Test device connectivity
    device_status = await govee.check_device_connectivity()
    diagnostics["tests"]["device_connectivity"] = device_status
    
    # Test data retrieval
    try:
        sensor_data = await govee.get_device_state(use_cache=False)
        diagnostics["tests"]["data_retrieval"] = {
            "status": "passed" if sensor_data.get("status") == "success" else "failed",
            "has_temperature": sensor_data.get("temperature") is not None,
            "has_humidity": sensor_data.get("humidity") is not None,
            "has_battery": sensor_data.get("battery_level") is not None,
            "device_id": sensor_data.get("device_id"),
            "capabilities_count": sensor_data.get("capabilities_count", 0)
        }
    except Exception as e:
        diagnostics["tests"]["data_retrieval"] = {"status": "failed", "error": str(e)}
    
    return diagnostics

@app.get("/")
async def root():
    return {
        "service": "Govee Sensor Integration Service",
        "version": "1.0.0",
        "description": "Govee smart sensor monitoring with real-time data collection and Redis pub/sub",
        "endpoints": [
            "/health - Health check",
            "/sensors/current - Get current sensor readings",
            "/devices - Get device information",
            "/diagnostics - Run system diagnostics"
        ],
        "timestamp": datetime.now(timezone.utc)
    }

def publish_health_status(redis_conn: redis.Redis, service: str, status: str, details: Dict):
    try:
        message = {
            "service": service,
            "status": status,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        redis_conn.publish("health-updates", json.dumps(message, default=str))
    except Exception as e:
        logger.error(f"Failed to publish health status: {e}")

def publish_sensor_data(redis_conn: redis.Redis, sensor_data: Dict):
    try:
        message = {
            "service": "govee",
            "type": "current_reading",
            "data": sensor_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        redis_conn.publish("sensor-data", json.dumps(message, default=str))
        temp = sensor_data.get('temperature', 'N/A')
        humidity = sensor_data.get('humidity', 'N/A')
        logger.info(f"Published Govee sensor data: {temp}°F, {humidity}%")
    except Exception as e:
        logger.error(f"Failed to publish sensor data: {e}")

def print_govee():
    print("Govee Service - Smart Sensor Integration Ready")

if __name__ == '__main__':
    print_govee()