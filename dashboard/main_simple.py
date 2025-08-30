import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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

class HealthDashboard:
    def __init__(self):
        self.services = {
            "hubitat": {"port": 8000, "name": "Hubitat Hub Control"},
            "weather": {"port": 8001, "name": "Weather Data Service"},
            "govee": {"port": 8002, "name": "Govee Sensor Service"},
            "database": {"port": 8003, "name": "Database Storage Service"}
        }
    
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
                    try:
                        data = await response.json()
                        return ServiceHealth(
                            service=service_name,
                            status=data.get("status", "unknown"),
                            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                            details=data.get("details", {}),
                            response_time_ms=response_time
                        )
                    except:
                        return ServiceHealth(
                            service=service_name,
                            status="responding",
                            timestamp=datetime.now(timezone.utc),
                            details={"name": name, "http_status": response.status},
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
                response_time_ms=10000
            )
        except Exception as e:
            return ServiceHealth(
                service=service_name,
                status="offline",
                timestamp=datetime.now(timezone.utc),
                details={"error": str(e), "name": name},
                response_time_ms=None
            )
    
    async def get_system_health(self):
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
        status_priority = {"healthy": 4, "responding": 3, "degraded": 2, "unhealthy": 1, "offline": 0, "timeout": 0, "error": 0}
        overall_status = "healthy"
        
        for health in service_healths:
            current_priority = status_priority.get(health.status, 0)
            overall_priority = status_priority.get(overall_status, 5)
            if current_priority < overall_priority:
                overall_status = health.status
        
        # Calculate summary statistics
        total_services = len(service_healths)
        healthy_services = sum(1 for h in service_healths if h.status in ["healthy", "responding", "degraded"])
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
        
        return {
            "overall_status": overall_status,
            "services": [health.dict() for health in service_healths],
            "summary": summary,
            "timestamp": datetime.now(timezone.utc)
        }

# Global variables
dashboard = HealthDashboard()

app = FastAPI(
    title="System Health Dashboard",
    version="1.0.0",
    description="Centralized health monitoring and status dashboard for all IoT services"
)

@app.get("/health")
async def dashboard_health():
    """Health check for the dashboard service itself."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc),
        "service": "dashboard"
    }

@app.get("/system")
async def get_system_health():
    """Get comprehensive system health status."""
    return await dashboard.get_system_health()

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
            .status-responding { border-left: 5px solid #2196F3; }
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
                <p><strong>Proto-Deployment Demo</strong></p>
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
        
        loadDashboard();
        setInterval(loadDashboard, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == '__main__':
    print("Simple Dashboard Service - IoT Monitoring Ready")