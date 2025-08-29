import os
import json
import sqlite3
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import redis
import threading
import pytz
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class SensorReading(BaseModel):
    sensor_id: str = Field(..., description="Unique identifier for the sensor")
    temperature: Optional[float] = Field(None, description="Temperature reading in Fahrenheit")
    humidity: Optional[float] = Field(None, description="Humidity percentage (0-100)")
    battery_level: Optional[int] = Field(None, description="Battery level percentage")
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @validator('temperature')
    def validate_temperature(cls, v):
        if v is not None and not (-100 <= v <= 150):
            raise ValueError('Temperature must be between -100 and 150 degrees')
        return v
    
    @validator('humidity')
    def validate_humidity(cls, v):
        if v is not None and not (0 <= v <= 100):
            raise ValueError('Humidity must be between 0 and 100 percent')
        return v

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    details: Dict[str, Any]

class QueryRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    sensor_ids: Optional[List[str]] = None

class DatabaseService:
    def __init__(self, db_path: str = "sensor_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with proper schema and indexes."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create main sensor readings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sensor_id TEXT NOT NULL,
                    temperature REAL,
                    humidity REAL,
                    battery_level INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(timestamp, sensor_id)
                )
            ''')
            
            # Create indexes for better query performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON sensor_readings(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sensor_id 
                ON sensor_readings(sensor_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sensor_timestamp 
                ON sensor_readings(sensor_id, timestamp)
            ''')
            
            # Create backup/archive table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_readings_archive (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME,
                    sensor_id TEXT,
                    temperature REAL,
                    humidity REAL,
                    battery_level INTEGER,
                    created_at DATETIME,
                    archived_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized successfully at {self.db_path}")
            
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    def store_reading(self, reading: SensorReading) -> Dict[str, Any]:
        """Store sensor reading with data integrity checks."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Use INSERT OR REPLACE to handle duplicates
            cursor.execute('''
                INSERT OR REPLACE INTO sensor_readings 
                (timestamp, sensor_id, temperature, humidity, battery_level)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                reading.timestamp.isoformat(),
                reading.sensor_id,
                reading.temperature,
                reading.humidity,
                reading.battery_level
            ))
            
            row_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            result = {
                "status": "success",
                "message": "Reading stored successfully",
                "row_id": row_id,
                "sensor_id": reading.sensor_id,
                "timestamp": reading.timestamp.isoformat()
            }
            
            logger.info(f"Stored reading for {reading.sensor_id}: {reading.temperature}°F, {reading.humidity}%")
            return result
            
        except sqlite3.Error as e:
            error_msg = f"SQLite error storing reading: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error storing reading: {e}"
            logger.exception(error_msg)
            return {"status": "error", "message": error_msg}
    
    def get_recent_readings(self, minutes: int = 60, sensor_id: Optional[str] = None) -> List[Dict]:
        """Get recent readings within specified time window."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            
            if sensor_id:
                cursor.execute('''
                    SELECT timestamp, sensor_id, temperature, humidity, battery_level
                    FROM sensor_readings 
                    WHERE timestamp >= ? AND sensor_id = ?
                    ORDER BY timestamp DESC
                ''', (cutoff_time.isoformat(), sensor_id))
            else:
                cursor.execute('''
                    SELECT timestamp, sensor_id, temperature, humidity, battery_level
                    FROM sensor_readings 
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                ''', (cutoff_time.isoformat(),))
            
            readings = []
            for row in cursor.fetchall():
                readings.append({
                    "timestamp": row[0],
                    "sensor_id": row[1],
                    "temperature": row[2],
                    "humidity": row[3],
                    "battery_level": row[4]
                })
            
            conn.close()
            return readings
            
        except sqlite3.Error as e:
            logger.error(f"SQLite error retrieving readings: {e}")
            return []
        except Exception as e:
            logger.exception(f"Unexpected error retrieving readings: {e}")
            return []
    
    def get_readings_for_period(self, start_time: datetime, end_time: datetime, 
                               sensor_ids: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """Get readings for specific time period, optionally filtered by sensor IDs."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            all_data = {}
            
            if sensor_ids:
                sensors_to_query = sensor_ids
            else:
                # Get all unique sensor IDs in the time range
                cursor.execute('''
                    SELECT DISTINCT sensor_id FROM sensor_readings
                    WHERE timestamp BETWEEN ? AND ?
                ''', (start_time.isoformat(), end_time.isoformat()))
                sensors_to_query = [row[0] for row in cursor.fetchall()]
            
            # Query each sensor
            for sensor_id in sensors_to_query:
                cursor.execute('''
                    SELECT timestamp, temperature, humidity, battery_level
                    FROM sensor_readings
                    WHERE timestamp BETWEEN ? AND ? AND sensor_id = ?
                    ORDER BY timestamp ASC
                ''', (start_time.isoformat(), end_time.isoformat(), sensor_id))
                
                readings = []
                for row in cursor.fetchall():
                    readings.append({
                        "timestamp": row[0],
                        "temperature": row[1],
                        "humidity": row[2],
                        "battery_level": row[3]
                    })
                
                all_data[sensor_id] = readings
            
            conn.close()
            return all_data
            
        except sqlite3.Error as e:
            logger.error(f"SQLite error retrieving period data: {e}")
            return {}
        except Exception as e:
            logger.exception(f"Unexpected error retrieving period data: {e}")
            return {}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics and health information."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Count total readings
            cursor.execute("SELECT COUNT(*) FROM sensor_readings")
            total_readings = cursor.fetchone()[0]
            
            # Count unique sensors
            cursor.execute("SELECT COUNT(DISTINCT sensor_id) FROM sensor_readings")
            unique_sensors = cursor.fetchone()[0]
            
            # Get oldest and newest readings
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM sensor_readings")
            oldest, newest = cursor.fetchone()
            
            # Get recent activity (last hour)
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            cursor.execute('''
                SELECT COUNT(*) FROM sensor_readings 
                WHERE timestamp >= ?
            ''', (one_hour_ago.isoformat(),))
            recent_readings = cursor.fetchone()[0]
            
            # Get database file size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            conn.close()
            
            return {
                "total_readings": total_readings,
                "unique_sensors": unique_sensors,
                "oldest_reading": oldest,
                "newest_reading": newest,
                "recent_readings_1h": recent_readings,
                "database_size_bytes": db_size,
                "database_path": self.db_path
            }
            
        except Exception as e:
            logger.exception(f"Error getting database stats: {e}")
            return {"error": str(e)}

# Global variables
db_service: Optional[DatabaseService] = None
redis_client: Optional[redis.Redis] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global db_service, redis_client
    
    # Startup
    try:
        db_service = DatabaseService()
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )
        
        # Test Redis connection
        redis_client.ping()
        
        # Start Redis subscriber for automatic data storage
        threading.Thread(target=redis_subscriber, daemon=True).start()
        
        print("✅ Database service started successfully")
    except Exception as e:
        print(f"❌ Failed to start Database service: {e}")
        raise
    
    yield
    
    # Shutdown
    if redis_client:
        redis_client.close()

app = FastAPI(
    title="Database Service",
    version="1.0.0",
    description="SQLite-based sensor data storage with Redis integration and data integrity",
    lifespan=lifespan
)

async def get_db_service() -> DatabaseService:
    if db_service is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    return db_service

async def get_redis_client() -> redis.Redis:
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis client not initialized")
    return redis_client

@app.get("/health", response_model=HealthCheck)
async def health_check(
    background_tasks: BackgroundTasks,
    db: DatabaseService = Depends(get_db_service),
    redis: redis.Redis = Depends(get_redis_client)
):
    health_details = {"service": "database", "version": "1.0.0"}
    
    try:
        # Check Redis connection
        redis.ping()
        health_details["redis"] = "connected"
        
        # Check database
        stats = db.get_database_stats()
        health_details["database"] = stats
        
        # Determine overall status
        overall_status = "healthy"
        if "error" in stats:
            overall_status = "degraded"
        
        # Publish health status
        background_tasks.add_task(publish_health_status, redis, "database", overall_status, health_details)
        
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

@app.post("/readings")
async def store_reading(
    reading: SensorReading,
    background_tasks: BackgroundTasks,
    db: DatabaseService = Depends(get_db_service),
    redis: redis.Redis = Depends(get_redis_client)
):
    result = db.store_reading(reading)
    
    if result.get("status") == "success":
        # Publish storage confirmation to Redis
        background_tasks.add_task(publish_storage_event, redis, result, reading.dict())
    
    return result

@app.get("/readings/recent")
async def get_recent_readings(
    minutes: int = 60,
    sensor_id: Optional[str] = None,
    db: DatabaseService = Depends(get_db_service)
):
    readings = db.get_recent_readings(minutes=minutes, sensor_id=sensor_id)
    return {
        "readings": readings,
        "count": len(readings),
        "time_window_minutes": minutes,
        "sensor_filter": sensor_id
    }

@app.post("/readings/query")
async def query_readings(
    query: QueryRequest,
    db: DatabaseService = Depends(get_db_service)
):
    data = db.get_readings_for_period(
        start_time=query.start_time,
        end_time=query.end_time,
        sensor_ids=query.sensor_ids
    )
    
    total_readings = sum(len(readings) for readings in data.values())
    
    return {
        "data": data,
        "total_readings": total_readings,
        "sensor_count": len(data),
        "time_range": {
            "start": query.start_time.isoformat(),
            "end": query.end_time.isoformat()
        }
    }

@app.get("/stats")
async def get_database_statistics(db: DatabaseService = Depends(get_db_service)):
    return db.get_database_stats()

@app.get("/")
async def root():
    return {
        "service": "Database Service - Sensor Data Storage",
        "version": "1.0.0",
        "description": "SQLite-based sensor data storage with Redis integration and comprehensive data integrity",
        "endpoints": [
            "/health - Health check with database statistics",
            "/readings - Store new sensor reading (POST)",
            "/readings/recent - Get recent readings with time filter",
            "/readings/query - Query readings by time range and sensors (POST)",
            "/stats - Database statistics and health"
        ],
        "timestamp": datetime.now(timezone.utc)
    }

def redis_subscriber():
    """Subscribe to Redis channels for automatic sensor data storage."""
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe("sensor-data", "weather-data")
        
        logger.info("Started Redis subscriber for automatic sensor and weather data storage")
        
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    
                    # Handle different data types based on channel
                    if message["channel"] == "sensor-data":
                        # Govee/sensor data format
                        sensor_data = data.get("data", {})
                        if sensor_data.get("status") == "success":
                            reading = SensorReading(
                                sensor_id=sensor_data.get("device_id", "unknown"),
                                temperature=sensor_data.get("temperature"),
                                humidity=sensor_data.get("humidity"),
                                battery_level=sensor_data.get("battery_level"),
                                timestamp=datetime.fromisoformat(sensor_data.get("timestamp", datetime.now(timezone.utc).isoformat()))
                            )
                            
                            result = db_service.store_reading(reading)
                            if result.get("status") == "success":
                                logger.info(f"Auto-stored sensor data from {reading.sensor_id}")
                            else:
                                logger.error(f"Failed to auto-store sensor data: {result}")
                    
                    elif message["channel"] == "weather-data":
                        # Weather data format
                        weather_data = data.get("data", {})
                        if weather_data.get("status") == "success":
                            reading = SensorReading(
                                sensor_id=f"weather_{weather_data.get('location', 'unknown')}",
                                temperature=weather_data.get("temperature"),
                                humidity=weather_data.get("humidity"),
                                battery_level=None,  # Weather API doesn't have battery
                                timestamp=datetime.fromisoformat(weather_data.get("timestamp", datetime.now(timezone.utc).isoformat()))
                            )
                            
                            result = db_service.store_reading(reading)
                            if result.get("status") == "success":
                                logger.info(f"Auto-stored weather data from {reading.sensor_id}")
                            else:
                                logger.error(f"Failed to auto-store weather data: {result}")
                            
                except Exception as e:
                    logger.error(f"Error processing Redis data: {e}")
                    
    except Exception as e:
        logger.error(f"Redis subscriber error: {e}")

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

def publish_storage_event(redis_conn: redis.Redis, result: Dict, reading_data: Dict):
    try:
        message = {
            "service": "database",
            "type": "reading_stored",
            "result": result,
            "reading": reading_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        redis_conn.publish("database-events", json.dumps(message, default=str))
    except Exception as e:
        logger.error(f"Failed to publish storage event: {e}")

def print_database():
    print("Database Service - SQLite Sensor Data Storage Ready")

if __name__ == '__main__':
    print_database()