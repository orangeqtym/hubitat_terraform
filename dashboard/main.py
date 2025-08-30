import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import redis
import threading
import aiohttp
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models
class ServiceHealth(BaseModel):
    service: str
    status: str
    timestamp: datetime
    details: Dict[str, Any]
    response_time_ms: Optional[float] = None

class SystemHealth(BaseModel):
    overall_status: str
    timestamp: datetime
    services: List[ServiceHealth]
    summary: Dict[str, Any]

class HealthDashboard:
    def __init__(self):
        self.services = {
            "hubitat": {"port": 8000, "name": "Hubitat Hub Control"},
            "weather": {"port": 8001, "name": "Weather Data Service"},
            "govee": {"port": 8002, "name": "Govee Sensor Service"},
            "database": {"port": 8003, "name": "Database Storage Service"}
        }
        self.health_cache = {}
        self.last_update = None
    
    async def check_service_health(self, session: aiohttp.ClientSession, service_name: str, service_info: Dict) -> ServiceHealth:
        """Check health of individual service."""
        port = service_info["port"]
        name = service_info["name"]
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Try to connect to service health endpoint
            async with session.get(f"http://localhost:{port}/health", timeout=aiohttp.ClientTimeout(total=10)) as response:
                response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    return ServiceHealth(
                        service=service_name,
                        status=data.get("status", "unknown"),
                        timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                        details=data.get("details", {}),
                        response_time_ms=response_time
                    )
                else:
                    return ServiceHealth(
                        service=service_name,
                        status="error",
                        timestamp=datetime.now(timezone.utc),
                        details={"error": f"HTTP {response.status}", "name": name},
                        response_time_ms=response_time
                    )
                    
        except asyncio.TimeoutError:
            return ServiceHealth(
                service=service_name,
                status="timeout",
                timestamp=datetime.now(timezone.utc),
                details={"error": "Request timeout", "name": name},
                response_time_ms=10000  # Timeout value
            )
        except Exception as e:
            return ServiceHealth(
                service=service_name,
                status="offline",
                timestamp=datetime.now(timezone.utc),
                details={"error": str(e), "name": name},
                response_time_ms=None
            )
    
    async def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health status."""
        service_healths = []
        
        # Check all services concurrently
        async with aiohttp.ClientSession() as session:
            tasks = []
            for service_name, service_info in self.services.items():
                task = self.check_service_health(session, service_name, service_info)
                tasks.append(task)
            
            service_healths = await asyncio.gather(*tasks)
        
        # Calculate overall status
        status_priority = {"healthy": 4, "degraded": 3, "unhealthy": 2, "offline": 1, "timeout": 1, "error": 1}
        overall_status = "healthy"
        
        for health in service_healths:
            current_priority = status_priority.get(health.status, 0)
            overall_priority = status_priority.get(overall_status, 5)
            if current_priority < overall_priority:
                overall_status = health.status
        
        # Calculate summary statistics
        total_services = len(service_healths)
        healthy_services = sum(1 for h in service_healths if h.status in ["healthy", "degraded"])
        offline_services = sum(1 for h in service_healths if h.status in ["offline", "timeout", "error"])
        avg_response_time = None
        
        response_times = [h.response_time_ms for h in service_healths if h.response_time_ms is not None]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
        
        summary = {
            "total_services": total_services,
            "healthy_services": healthy_services,
            "offline_services": offline_services,
            "avg_response_time_ms": avg_response_time,
            "uptime_percentage": (healthy_services / total_services * 100) if total_services > 0 else 0
        }
        
        # Cache the results
        self.health_cache = {
            "overall_status": overall_status,
            "services": [health.dict() for health in service_healths],
            "summary": summary,
            "last_update": datetime.now(timezone.utc)
        }
        self.last_update = datetime.now(timezone.utc)
        
        return SystemHealth(
            overall_status=overall_status,
            timestamp=datetime.now(timezone.utc),
            services=service_healths,
            summary=summary
        )
    
    def get_cached_health(self) -> Optional[Dict]:
        """Get cached health data if recent enough."""
        if self.last_update and self.health_cache:
            # Return cache if less than 30 seconds old
            if (datetime.now(timezone.utc) - self.last_update).total_seconds() < 30:
                return self.health_cache
        return None

# Global variables
dashboard: Optional[HealthDashboard] = None
redis_client: Optional[redis.Redis] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global dashboard, redis_client
    
    # Startup
    try:
        dashboard = HealthDashboard()
        redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True
        )
        
        # Test Redis connection
        redis_client.ping()
        
        # Start health monitoring background task
        asyncio.create_task(health_monitor())
        
        print("✅ Dashboard service started successfully")
    except Exception as e:
        print(f"❌ Failed to start Dashboard service: {e}")
        # Don't raise - dashboard can work without Redis
    
    yield
    
    # Shutdown
    if redis_client:
        redis_client.close()

app = FastAPI(
    title="System Health Dashboard",
    version="1.0.1",
    description="Centralized health monitoring and status dashboard for all IoT services",
    lifespan=lifespan
)

async def get_dashboard() -> HealthDashboard:
    if dashboard is None:
        raise HTTPException(status_code=503, detail="Dashboard service not initialized")
    return dashboard

@app.get("/health")
async def dashboard_health():
    """Health check for the dashboard service itself."""
    try:
        # Quick connectivity test
        test_health = {"status": "healthy", "timestamp": datetime.now(timezone.utc)}
        
        if redis_client:
            try:
                redis_client.ping()
                test_health["redis"] = "connected"
            except:
                test_health["redis"] = "disconnected"
                test_health["status"] = "degraded"
        
        return test_health
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc),
            "error": str(e)
        }

@app.get("/system", response_model=SystemHealth)
async def get_system_health(
    use_cache: bool = True,
    dashboard_service: HealthDashboard = Depends(get_dashboard)
):
    """Get comprehensive system health status."""
    
    # Try cache first if requested
    if use_cache:
        cached = dashboard_service.get_cached_health()
        if cached:
            return SystemHealth(
                overall_status=cached["overall_status"],
                timestamp=cached["last_update"],
                services=[ServiceHealth(**service) for service in cached["services"]],
                summary=cached["summary"]
            )
    
    # Get fresh health data
    return await dashboard_service.get_system_health()

@app.get("/system/summary")
async def get_system_summary(dashboard_service: HealthDashboard = Depends(get_dashboard)):
    """Get quick system summary."""
    health = await dashboard_service.get_system_health()
    return {
        "overall_status": health.overall_status,
        "summary": health.summary,
        "timestamp": health.timestamp
    }

@app.get("/services/{service_name}")
async def get_service_detail(
    service_name: str,
    dashboard_service: HealthDashboard = Depends(get_dashboard)
):
    """Get detailed information about a specific service."""
    if service_name not in dashboard_service.services:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    # Get fresh health check for this service
    async with aiohttp.ClientSession() as session:
        health = await dashboard_service.check_service_health(
            session, 
            service_name, 
            dashboard_service.services[service_name]
        )
    
    return health

@app.get("/", response_class=HTMLResponse)
async def dashboard_ui():
    """Serve a simple HTML dashboard."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>IoT System Health Dashboard</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .status-card { background: white; border-radius: 8px; padding: 20px; margin: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .status-healthy { border-left: 5px solid #4CAF50; }
            .status-degraded { border-left: 5px solid #FF9800; }
            .status-unhealthy { border-left: 5px solid #F44336; }
            .status-offline { border-left: 5px solid #9E9E9E; }
            .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }
            .service-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
            .metric { text-align: center; padding: 15px; }
            .metric-value { font-size: 24px; font-weight: bold; color: #333; }
            .metric-label { color: #666; font-size: 14px; }
            .timestamp { color: #888; font-size: 12px; text-align: center; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏠 IoT System Health Dashboard</h1>
                <p>Real-time monitoring of all connected services</p>
            </div>
            
            <div id="content">Loading...</div>
        </div>
        
        <script>
        async function loadDashboard() {
            try {
                const response = await fetch('/system');
                const data = await response.json();
                
                let html = '<div class="summary">';
                html += `<div class="status-card metric">
                    <div class="metric-value">${data.overall_status.toUpperCase()}</div>
                    <div class="metric-label">Overall Status</div>
                </div>`;
                html += `<div class="status-card metric">
                    <div class="metric-value">${data.summary.healthy_services}/${data.summary.total_services}</div>
                    <div class="metric-label">Services Online</div>
                </div>`;
                html += `<div class="status-card metric">
                    <div class="metric-value">${data.summary.uptime_percentage.toFixed(1)}%</div>
                    <div class="metric-label">System Uptime</div>
                </div>`;
                if (data.summary.avg_response_time_ms) {
                    html += `<div class="status-card metric">
                        <div class="metric-value">${data.summary.avg_response_time_ms.toFixed(0)}ms</div>
                        <div class="metric-label">Avg Response Time</div>
                    </div>`;
                }
                html += '</div>';
                
                html += '<div class="service-grid">';
                data.services.forEach(service => {
                    const statusClass = `status-${service.status}`;
                    html += `<div class="status-card ${statusClass}">
                        <h3>${service.service.charAt(0).toUpperCase() + service.service.slice(1)} Service</h3>
                        <p><strong>Status:</strong> ${service.status}</p>
                        <p><strong>Response Time:</strong> ${service.response_time_ms ? service.response_time_ms.toFixed(0) + 'ms' : 'N/A'}</p>
                        <p><strong>Last Check:</strong> ${new Date(service.timestamp).toLocaleTimeString()}</p>`;
                    
                    if (service.details) {
                        html += '<details><summary>Details</summary><pre>' + JSON.stringify(service.details, null, 2) + '</pre></details>';
                    }
                    
                    html += '</div>';
                });
                html += '</div>';
                
                html += `<div class="timestamp">Last updated: ${new Date(data.timestamp).toLocaleString()}</div>`;
                
                document.getElementById('content').innerHTML = html;
            } catch (error) {
                document.getElementById('content').innerHTML = '<div class="status-card status-unhealthy"><h3>Error loading dashboard</h3><p>' + error.message + '</p></div>';
            }
        }
        
        // Load immediately and refresh every 30 seconds
        loadDashboard();
        setInterval(loadDashboard, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/data")
async def get_sensor_data(minutes: int = 60):
    """Get recent sensor data for visualization."""
    try:
        # Fetch data from database service
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"http://database:8000/readings/recent?minutes={minutes}") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Process data for visualization
                    readings = data.get("readings", [])
                    
                    # Group by sensor
                    sensors = {}
                    for reading in readings:
                        sensor_id = reading["sensor_id"]
                        if sensor_id not in sensors:
                            sensors[sensor_id] = {"data": [], "latest": None}
                        
                        sensors[sensor_id]["data"].append({
                            "timestamp": reading["timestamp"],
                            "temperature": reading["temperature"],
                            "humidity": reading["humidity"],
                            "battery_level": reading["battery_level"]
                        })
                        
                        # Keep track of latest reading
                        if not sensors[sensor_id]["latest"] or reading["timestamp"] > sensors[sensor_id]["latest"]["timestamp"]:
                            sensors[sensor_id]["latest"] = reading
                    
                    return {
                        "sensors": sensors,
                        "total_readings": data.get("count", 0),
                        "time_window_minutes": minutes,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                else:
                    return {"error": "Failed to fetch sensor data", "status": response.status}
                    
    except Exception as e:
        logger.error(f"Error fetching sensor data: {e}")
        return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/charts")
async def sensor_charts():
    """Serve a basic charts page for sensor data visualization."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>IoT Sensor Data Charts</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { text-align: center; margin-bottom: 30px; }
            .chart-container { background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .controls { text-align: center; margin: 20px 0; }
            select, button { padding: 8px 12px; margin: 0 5px; }
            .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
            .metric-card { background: white; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .metric-value { font-size: 24px; font-weight: bold; color: #333; }
            .metric-label { color: #666; font-size: 14px; }
            .loading { text-align: center; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 IoT Sensor Data Charts</h1>
                <p>Real-time temperature and humidity monitoring</p>
            </div>
            
            <div class="controls">
                <select id="timeRange">
                    <option value="60">Last Hour</option>
                    <option value="360">Last 6 Hours</option>
                    <option value="1440">Last 24 Hours</option>
                    <option value="10080">Last Week</option>
                </select>
                <button onclick="loadCharts()">Refresh</button>
                <button onclick="toggleAutoRefresh()">Auto Refresh: <span id="autoStatus">OFF</span></button>
            </div>
            
            <div id="metrics" class="metrics"></div>
            
            <div class="chart-container">
                <canvas id="temperatureChart"></canvas>
            </div>
            
            <div class="chart-container">
                <canvas id="humidityChart"></canvas>
            </div>
            
            <div id="loadingMessage" class="loading">Loading sensor data...</div>
        </div>
        
        <script>
        let temperatureChart = null;
        let humidityChart = null;
        let autoRefreshInterval = null;
        let isAutoRefresh = false;
        
        async function loadCharts() {
            const timeRange = document.getElementById('timeRange').value;
            const loadingEl = document.getElementById('loadingMessage');
            loadingEl.style.display = 'block';
            
            try {
                const response = await fetch(`/data?minutes=${timeRange}`);
                const data = await response.json();
                
                if (data.error) {
                    throw new Error(data.error);
                }
                
                updateMetrics(data);
                updateCharts(data);
                loadingEl.style.display = 'none';
                
            } catch (error) {
                console.error('Error loading charts:', error);
                loadingEl.innerHTML = `<p style="color: red;">Error loading data: ${error.message}</p>`;
            }
        }
        
        function updateMetrics(data) {
            const metricsEl = document.getElementById('metrics');
            const sensors = data.sensors || {};
            
            let html = '';
            html += `<div class="metric-card">
                <div class="metric-value">${Object.keys(sensors).length}</div>
                <div class="metric-label">Active Sensors</div>
            </div>`;
            html += `<div class="metric-card">
                <div class="metric-value">${data.total_readings}</div>
                <div class="metric-label">Total Readings</div>
            </div>`;
            
            // Show latest readings for each sensor
            Object.entries(sensors).forEach(([sensorId, sensorData]) => {
                const latest = sensorData.latest;
                if (latest) {
                    html += `<div class="metric-card">
                        <div class="metric-value">${latest.temperature ? latest.temperature.toFixed(1) + '°F' : 'N/A'}</div>
                        <div class="metric-label">${sensorId} Temperature</div>
                    </div>`;
                    html += `<div class="metric-card">
                        <div class="metric-value">${latest.humidity ? latest.humidity.toFixed(1) + '%' : 'N/A'}</div>
                        <div class="metric-label">${sensorId} Humidity</div>
                    </div>`;
                }
            });
            
            metricsEl.innerHTML = html;
        }
        
        function updateCharts(data) {
            const sensors = data.sensors || {};
            
            // Prepare chart data
            const datasets = [];
            const colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'];
            let colorIndex = 0;
            
            Object.entries(sensors).forEach(([sensorId, sensorData]) => {
                const tempData = [];
                const humidityData = [];
                const labels = [];
                
                sensorData.data.forEach(reading => {
                    const time = new Date(reading.timestamp);
                    labels.push(time.toLocaleTimeString());
                    tempData.push(reading.temperature);
                    humidityData.push(reading.humidity);
                });
                
                datasets.push({
                    temperature: {
                        label: sensorId,
                        data: tempData,
                        borderColor: colors[colorIndex % colors.length],
                        backgroundColor: colors[colorIndex % colors.length] + '20',
                        fill: false,
                        tension: 0.1
                    },
                    humidity: {
                        label: sensorId,
                        data: humidityData,
                        borderColor: colors[colorIndex % colors.length],
                        backgroundColor: colors[colorIndex % colors.length] + '20',
                        fill: false,
                        tension: 0.1
                    },
                    labels: labels
                });
                
                colorIndex++;
            });
            
            // Update temperature chart
            if (temperatureChart) {
                temperatureChart.destroy();
            }
            
            const tempCtx = document.getElementById('temperatureChart').getContext('2d');
            temperatureChart = new Chart(tempCtx, {
                type: 'line',
                data: {
                    labels: datasets[0]?.labels || [],
                    datasets: datasets.map(ds => ds.temperature).filter(ds => ds)
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Temperature Over Time (°F)'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            title: {
                                display: true,
                                text: 'Temperature (°F)'
                            }
                        }
                    }
                }
            });
            
            // Update humidity chart
            if (humidityChart) {
                humidityChart.destroy();
            }
            
            const humidityCtx = document.getElementById('humidityChart').getContext('2d');
            humidityChart = new Chart(humidityCtx, {
                type: 'line',
                data: {
                    labels: datasets[0]?.labels || [],
                    datasets: datasets.map(ds => ds.humidity).filter(ds => ds)
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Humidity Over Time (%)'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Humidity (%)'
                            }
                        }
                    }
                }
            });
        }
        
        function toggleAutoRefresh() {
            const statusEl = document.getElementById('autoStatus');
            
            if (isAutoRefresh) {
                clearInterval(autoRefreshInterval);
                isAutoRefresh = false;
                statusEl.textContent = 'OFF';
            } else {
                autoRefreshInterval = setInterval(loadCharts, 30000);
                isAutoRefresh = true;
                statusEl.textContent = 'ON';
            }
        }
        
        // Load charts on page load
        loadCharts();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

async def health_monitor():
    """Background task to monitor system health and publish to Redis."""
    while True:
        try:
            if dashboard and redis_client:
                health = await dashboard.get_system_health()
                
                # Publish system health to Redis
                message = {
                    "overall_status": health.overall_status,
                    "summary": health.summary,
                    "services": [service.dict() for service in health.services],
                    "timestamp": health.timestamp.isoformat()
                }
                
                redis_client.publish("system-health", json.dumps(message, default=str))
                logger.info(f"Published system health: {health.overall_status} ({health.summary['healthy_services']}/{health.summary['total_services']} services)")
            
            # Wait 1 minute before next check
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
            await asyncio.sleep(60)

def print_dashboard():
    print("System Health Dashboard - Centralized IoT Monitoring Ready")

if __name__ == '__main__':
    print_dashboard()