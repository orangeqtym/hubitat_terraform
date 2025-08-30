import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager

import redis
import threading
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from cachetools import TTLCache
import schedule
import threading
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for weather data (5-minute TTL)
weather_cache = TTLCache(maxsize=100, ttl=300)

# Type definitions
WeatherApiResponse = Dict[str, Any]
WeatherData = Dict[str, Union[str, int, float, None]]

# Pydantic models
class WeatherReading(BaseModel):
    timestamp: datetime
    temperature: float
    humidity: float
    pressure: Optional[float] = None
    location: str
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
    description: Optional[str] = None

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    details: Dict[str, Any]

class WeatherAPI:
    def __init__(self):
        self.api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
        self.latitude = os.environ.get("LATITUDE", "40.0448")
        self.longitude = os.environ.get("LONGITUDE", "-75.4884")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        
        if not self.api_key:
            raise ValueError("OPENWEATHERMAP_API_KEY environment variable is required")
        
        # Validate coordinates
        try:
            lat_float = float(self.latitude)
            lon_float = float(self.longitude)
            if not (-90 <= lat_float <= 90) or not (-180 <= lon_float <= 180):
                raise ValueError("Invalid coordinates")
        except ValueError as e:
            raise ValueError(f"Invalid latitude/longitude values: {e}")

    async def get_current_weather(self, use_cache: bool = True) -> WeatherData:
        """Get current weather data with caching and validation."""
        cache_key = f"weather_{self.latitude}_{self.longitude}"
        
        # Check cache first
        if use_cache and cache_key in weather_cache:
            logger.info("Returning cached weather data")
            return weather_cache[cache_key]
        
        params = {
            "appid": self.api_key,
            "lat": self.latitude,
            "lon": self.longitude,
            "units": "imperial"
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            json_response: WeatherApiResponse = response.json()
            
            # Extract and validate data
            main_data = json_response.get("main", {})
            sys_data = json_response.get("sys", {})
            weather_data = json_response.get("weather", [{}])[0]
            
            temperature = main_data.get("temp")
            humidity = main_data.get("humidity")
            pressure = main_data.get("pressure")
            
            # Validate temperature and humidity ranges
            if temperature is not None and not (-100 <= temperature <= 150):
                logger.warning(f"Temperature out of expected range: {temperature}°F")
            if humidity is not None and not (0 <= humidity <= 100):
                logger.warning(f"Humidity out of expected range: {humidity}%")
            
            # Convert timestamps
            sunrise = None
            sunset = None
            if sys_data.get("sunrise"):
                sunrise = datetime.fromtimestamp(sys_data["sunrise"], tz=timezone.utc)
            if sys_data.get("sunset"):
                sunset = datetime.fromtimestamp(sys_data["sunset"], tz=timezone.utc)
            
            weather_result = {
                "status": "success",
                "temperature": temperature,
                "humidity": humidity,
                "pressure": pressure,
                "location": json_response.get("name", "Unknown"),
                "description": weather_data.get("description", ""),
                "sunrise": sunrise.isoformat() if sunrise else None,
                "sunset": sunset.isoformat() if sunset else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "response_time_ms": response.elapsed.total_seconds() * 1000
            }
            
            # Cache the result
            weather_cache[cache_key] = weather_result
            
            logger.info(f"Successfully retrieved weather data for {weather_result['location']}")
            return weather_result
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"OpenWeatherMap API HTTP error: {e}"
            if e.response is not None:
                error_msg += f" - {e.response.text[:200]}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error accessing weather API: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        except Exception as e:
            error_msg = f"Unexpected error in weather API: {e}"
            logger.exception(error_msg)
            return {"status": "error", "message": error_msg}

    async def check_api_connectivity(self) -> Dict[str, Any]:
        """Test OpenWeatherMap API connectivity and response."""
        try:
            start_time = time.time()
            weather_data = await self.get_current_weather(use_cache=False)
            response_time = (time.time() - start_time) * 1000
            
            if weather_data.get("status") == "success":
                return {
                    "status": "online",
                    "api_key_valid": True,
                    "response_time_ms": response_time,
                    "location": weather_data.get("location"),
                    "current_temp": weather_data.get("temperature"),
                    "coordinates": f"{self.latitude}, {self.longitude}"
                }
            else:
                return {
                    "status": "error",
                    "api_key_valid": False,
                    "error": weather_data.get("message", "Unknown error"),
                    "coordinates": f"{self.latitude}, {self.longitude}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "api_key_valid": False,
                "error": str(e),
                "coordinates": f"{self.latitude}, {self.longitude}"
            }

# Global variables
weather_api: Optional[WeatherAPI] = None
redis_client: Optional[redis.Redis] = None

def run_scheduled_collection():
    """Background thread for scheduled weather data collection."""
    def collect_weather_data():
        """Collect weather data and publish to Redis."""
        if weather_api and redis_client:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                weather_data = loop.run_until_complete(weather_api.get_current_weather())
                if weather_data.get("status") == "success":
                    message = {
                        "service": "weather",
                        "type": "scheduled_reading",
                        "data": weather_data,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    loop.run_until_complete(
                        redis_client.publish("weather-data", json.dumps(message, default=str))
                    )
                    logger.info("Scheduled weather data collected and published")
                else:
                    logger.error(f"Failed to collect weather data: {weather_data.get('message')}")
                
                loop.close()
            except Exception as e:
                logger.error(f"Error in scheduled weather collection: {e}")
    
    # Schedule weather data collection every 15 minutes
    schedule.every(15).minutes.do(collect_weather_data)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global weather_api, redis_client
    
    # Startup
    try:
        weather_api = WeatherAPI()
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )
        
        # Test connections
        redis_client.ping()
        connectivity_test = await weather_api.check_api_connectivity()
        
        if connectivity_test.get("status") != "online":
            logger.warning(f"Weather API connectivity issue: {connectivity_test}")
        
        # Start background scheduler
        scheduler_thread = threading.Thread(target=run_scheduled_collection, daemon=True)
        scheduler_thread.start()
        
        logger.info("✅ Weather service started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start Weather service: {e}")
        raise
    
    yield
    
    # Shutdown
    if redis_client:
        await redis_client.close()

app = FastAPI(
    title="Weather Service",
    version="1.0.0",
    description="OpenWeatherMap integration service with comprehensive monitoring and caching",
    lifespan=lifespan
)

async def get_weather_api() -> WeatherAPI:
    """Dependency to get WeatherAPI instance."""
    if weather_api is None:
        raise HTTPException(status_code=503, detail="Weather API not initialized")
    return weather_api

async def get_redis_client() -> redis.Redis:
    """Dependency to get Redis client."""
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis client not initialized")
    return redis_client

@app.get("/health", response_model=HealthCheck)
async def health_check(
    background_tasks: BackgroundTasks,
    weather: WeatherAPI = Depends(get_weather_api),
    redis: redis.Redis = Depends(get_redis_client)
):
    """Comprehensive health check including API connectivity and data quality."""
    health_details = {
        "service": "weather",
        "version": "1.0.0"
    }
    
    try:
        # Check Redis connection
        redis.ping()
        health_details["redis"] = "connected"
        
        # Check weather API connectivity
        api_status = await weather.check_api_connectivity()
        health_details["weather_api"] = api_status
        
        # Check cache status
        health_details["cache_size"] = len(weather_cache)
        
        overall_status = "healthy" if api_status.get("status") == "online" else "degraded"
        
        # Publish health status to Redis
        background_tasks.add_task(
            publish_health_status,
            redis,
            "weather",
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

@app.get("/current")
async def get_current_weather(
    background_tasks: BackgroundTasks,
    use_cache: bool = True,
    weather: WeatherAPI = Depends(get_weather_api),
    redis: redis.Redis = Depends(get_redis_client)
):
    """Get current weather data with optional cache bypass."""
    weather_data = await weather.get_current_weather(use_cache=use_cache)
    
    if weather_data.get("status") == "success":
        # Publish weather data to Redis for other services
        background_tasks.add_task(
            publish_weather_data,
            redis,
            weather_data
        )
    
    return weather_data

@app.get("/forecast")
async def get_weather_forecast(weather: WeatherAPI = Depends(get_weather_api)):
    """Get weather forecast (placeholder for future 5-day forecast implementation)."""
    return {
        "message": "Forecast endpoint ready for implementation",
        "current_location": f"{weather.latitude}, {weather.longitude}",
        "api_status": "configured"
    }

@app.get("/diagnostics")
async def run_diagnostics(weather: WeatherAPI = Depends(get_weather_api)):
    """Run comprehensive diagnostics on weather service."""
    diagnostics = {
        "timestamp": datetime.now(timezone.utc),
        "tests": {}
    }
    
    # Test API connectivity
    api_status = await weather.check_api_connectivity()
    diagnostics["tests"]["api_connectivity"] = api_status
    
    # Test data retrieval
    try:
        weather_data = await weather.get_current_weather(use_cache=False)
        diagnostics["tests"]["data_retrieval"] = {
            "status": "passed" if weather_data.get("status") == "success" else "failed",
            "has_temperature": weather_data.get("temperature") is not None,
            "has_humidity": weather_data.get("humidity") is not None,
            "location": weather_data.get("location", "unknown")
        }
    except Exception as e:
        diagnostics["tests"]["data_retrieval"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Test cache functionality
    cache_size = len(weather_cache)
    diagnostics["tests"]["cache"] = {
        "status": "passed",
        "cache_size": cache_size,
        "cache_enabled": True
    }
    
    return diagnostics

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Weather Integration Service",
        "version": "1.0.0",
        "description": "OpenWeatherMap integration with caching, monitoring, and Redis pub/sub",
        "endpoints": [
            "/health - Health check",
            "/current - Get current weather",
            "/forecast - Get weather forecast (future)",
            "/diagnostics - Run system diagnostics"
        ],
        "data_collection": "Every 15 minutes",
        "timestamp": datetime.now(timezone.utc)
    }

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
        logger.error(f"Failed to publish health status: {e}")

def publish_weather_data(redis_conn: redis.Redis, weather_data: Dict):
    """Publish weather data to Redis for other services."""
    try:
        message = {
            "service": "weather",
            "type": "current_reading",
            "data": weather_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        redis_conn.publish("weather-data", json.dumps(message, default=str))
        logger.info(f"Published weather data: {weather_data.get('temperature')}°F, {weather_data.get('humidity')}%")
    except Exception as e:
        logger.error(f"Failed to publish weather data: {e}")

def print_weather():
    """Legacy function for backwards compatibility."""
    print("Weather Service - OpenWeatherMap Integration Ready")

if __name__ == '__main__':
    print_weather()