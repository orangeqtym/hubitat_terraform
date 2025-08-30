#!/usr/bin/env python3
"""
Device Discovery and Health Check Script
Run this before starting the integration to identify devices and validate connectivity.
"""

import os
import sys
import subprocess
import socket
import requests
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import uuid

@dataclass
class DeviceStatus:
    name: str
    type: str
    address: str
    port: Optional[int]
    status: str  # "online", "offline", "error", "unknown"
    details: Dict
    last_checked: datetime

class DeviceDiscovery:
    def __init__(self):
        self.devices: List[DeviceStatus] = []
        self.load_environment()
        
    def load_environment(self):
        """Load environment variables from .env file if it exists."""
        env_files = [
            "C:\\Users\\orang\\PycharmProjects\\HubitatApiPlayground\\.env",
            ".env"
        ]
        
        for env_file in env_files:
            if os.path.exists(env_file):
                print(f"Loading environment from: {env_file}")
                with open(env_file, 'r') as f:
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            if value and not os.environ.get(key):
                                os.environ[key] = value
                break
        else:
            print("WARNING: No .env file found. Please ensure environment variables are set.")

    def ping_host(self, host: str) -> Tuple[bool, Dict]:
        """Ping a host to check basic network connectivity."""
        try:
            if sys.platform.startswith('win'):
                result = subprocess.run(['ping', '-n', '1', host], 
                                      capture_output=True, text=True, timeout=5)
            else:
                result = subprocess.run(['ping', '-c', '1', host], 
                                      capture_output=True, text=True, timeout=5)
            
            success = result.returncode == 0
            return success, {
                "command": result.args,
                "return_code": result.returncode,
                "output": result.stdout[:200] if success else result.stderr[:200]
            }
        except subprocess.TimeoutExpired:
            return False, {"error": "Ping timeout"}
        except Exception as e:
            return False, {"error": str(e)}

    def check_port(self, host: str, port: int, timeout: int = 3) -> Tuple[bool, Dict]:
        """Check if a specific port is open on a host."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            is_open = result == 0
            return is_open, {
                "host": host,
                "port": port,
                "result_code": result,
                "status": "open" if is_open else "closed"
            }
        except Exception as e:
            return False, {"error": str(e)}

    def discover_hubitat(self):
        """Discover and check Hubitat hub connectivity."""
        print("Checking Hubitat Hub...")
        
        hubitat_ip = os.environ.get("HUBITAT_IP")
        access_token = os.environ.get("HUBITAT_ACCESS_TOKEN")
        app_id = os.environ.get("HUBITAT_APP_ID")
        
        if not all([hubitat_ip, access_token, app_id]):
            self.devices.append(DeviceStatus(
                name="Hubitat Hub",
                type="hub",
                address="unknown",
                port=80,
                status="error",
                details={"error": "Missing environment variables: HUBITAT_IP, HUBITAT_ACCESS_TOKEN, or HUBITAT_APP_ID"},
                last_checked=datetime.now()
            ))
            return
        
        # Check basic network connectivity
        ping_success, ping_details = self.ping_host(hubitat_ip)
        port_open, port_details = self.check_port(hubitat_ip, 80)
        
        details = {
            "ip": hubitat_ip,
            "ping": ping_details,
            "port_80": port_details,
            "has_credentials": bool(access_token and app_id)
        }
        
        if ping_success and port_open:
            # Try to make an API call
            try:
                url = f"http://{hubitat_ip}/apps/api/{app_id}/devices/all"
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    devices_data = response.json()
                    details["api_status"] = "success"
                    details["device_count"] = len(devices_data) if isinstance(devices_data, list) else "unknown"
                    details["sample_devices"] = devices_data[:3] if isinstance(devices_data, list) else None
                    status = "online"
                else:
                    details["api_status"] = "failed"
                    details["api_error"] = f"HTTP {response.status_code}: {response.text[:200]}"
                    status = "error"
                    
            except requests.RequestException as e:
                details["api_status"] = "failed"
                details["api_error"] = str(e)
                status = "error"
        else:
            status = "offline"
        
        self.devices.append(DeviceStatus(
            name="Hubitat Hub",
            type="hub",
            address=hubitat_ip,
            port=80,
            status=status,
            details=details,
            last_checked=datetime.now()
        ))

    def discover_weather_api(self):
        """Check OpenWeatherMap API connectivity."""
        print("Checking OpenWeatherMap API...")
        
        api_key = os.environ.get("OPENWEATHERMAP_API_KEY")
        lat = os.environ.get("LATITUDE", "40.0448")
        lon = os.environ.get("LONGITUDE", "-75.4884")
        
        details = {
            "has_api_key": bool(api_key),
            "latitude": lat,
            "longitude": lon
        }
        
        if not api_key:
            self.devices.append(DeviceStatus(
                name="OpenWeatherMap API",
                type="external_api",
                address="api.openweathermap.org",
                port=443,
                status="error",
                details={**details, "error": "Missing OPENWEATHERMAP_API_KEY"},
                last_checked=datetime.now()
            ))
            return
        
        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "appid": api_key,
                "lat": lat,
                "lon": lon,
                "units": "imperial"
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                weather_data = response.json()
                details.update({
                    "api_status": "success",
                    "location": weather_data.get("name", "Unknown"),
                    "current_temp": weather_data.get("main", {}).get("temp"),
                    "current_humidity": weather_data.get("main", {}).get("humidity")
                })
                status = "online"
            else:
                details.update({
                    "api_status": "failed",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                })
                status = "error"
                
        except requests.RequestException as e:
            details.update({
                "api_status": "failed",
                "error": str(e)
            })
            status = "error"
        
        self.devices.append(DeviceStatus(
            name="OpenWeatherMap API",
            type="external_api",
            address="api.openweathermap.org",
            port=443,
            status=status,
            details=details,
            last_checked=datetime.now()
        ))

    def discover_govee_devices(self):
        """Check Govee API and device connectivity."""
        print("Checking Govee Devices...")
        
        api_key = os.environ.get("GOVEE_API_KEY")
        sku = os.environ.get("GOVEE_SKU")
        device_id = os.environ.get("GOVEE_DEVICE")
        
        details = {
            "has_api_key": bool(api_key),
            "has_sku": bool(sku),
            "has_device_id": bool(device_id)
        }
        
        if not all([api_key, sku, device_id]):
            self.devices.append(DeviceStatus(
                name="Govee Device",
                type="sensor",
                address="openapi.api.govee.com",
                port=443,
                status="error",
                details={**details, "error": "Missing GOVEE_API_KEY, GOVEE_SKU, or GOVEE_DEVICE"},
                last_checked=datetime.now()
            ))
            return
        
        try:
            request_id = str(uuid.uuid4())
            url = "https://openapi.api.govee.com/router/api/v1/device/state"
            headers = {
                "Content-Type": "application/json",
                "Govee-API-Key": api_key
            }
            payload = {
                "requestId": request_id,
                "payload": {
                    "sku": sku,
                    "device": device_id
                }
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                capabilities = data.get('payload', {}).get('capabilities', [])
                
                # Try to extract temperature and humidity
                temp = None
                humidity = None
                if len(capabilities) > 1:
                    temp = capabilities[1].get('state', {}).get('value')
                if len(capabilities) > 2:
                    hum_data = capabilities[2].get('state', {}).get('value')
                    if isinstance(hum_data, dict):
                        humidity = hum_data.get('currentHumidity')
                    elif isinstance(hum_data, (int, float)):
                        humidity = hum_data
                
                details.update({
                    "api_status": "success",
                    "temperature": temp,
                    "humidity": humidity,
                    "capabilities_count": len(capabilities),
                    "device_sku": sku,
                    "device_id": device_id
                })
                status = "online"
            else:
                details.update({
                    "api_status": "failed",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                })
                status = "error"
                
        except requests.RequestException as e:
            details.update({
                "api_status": "failed",
                "error": str(e)
            })
            status = "error"
        
        self.devices.append(DeviceStatus(
            name="Govee Device",
            type="sensor",
            address="openapi.api.govee.com",
            port=443,
            status=status,
            details=details,
            last_checked=datetime.now()
        ))

    def scan_network_devices(self):
        """Scan local network for common IoT device ports."""
        print("Scanning network for IoT devices...")
        
        # Common IoT device ports and protocols
        common_ports = [
            (80, "HTTP"),
            (443, "HTTPS"), 
            (8080, "HTTP-Alt"),
            (8443, "HTTPS-Alt"),
            (1883, "MQTT"),
            (8883, "MQTT-SSL"),
            (5353, "mDNS"),
            (8123, "Home Assistant")
        ]
        
        # Get local network range (simplified approach)
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            print(f"Local IP: {local_ip}")
            
            # Extract network prefix (assumes /24 subnet)
            network_prefix = '.'.join(local_ip.split('.')[:-1])
            
            # Quick scan of common IoT device IPs
            common_iot_ips = [
                f"{network_prefix}.1",    # Router
                f"{network_prefix}.2",    # Common device
                f"{network_prefix}.10",   # Common device
                f"{network_prefix}.100",  # Common device
                f"{network_prefix}.150",  # Common device
                f"{network_prefix}.200",  # Common device
            ]
            
            for ip in common_iot_ips:
                ping_success, ping_details = self.ping_host(ip)
                if ping_success:
                    open_ports = []
                    for port, service in common_ports:
                        port_open, _ = self.check_port(ip, port, timeout=1)
                        if port_open:
                            open_ports.append(f"{port}({service})")
                    
                    if open_ports:
                        self.devices.append(DeviceStatus(
                            name=f"Network Device {ip}",
                            type="unknown_device",
                            address=ip,
                            port=None,
                            status="online",
                            details={
                                "open_ports": open_ports,
                                "ping": ping_details
                            },
                            last_checked=datetime.now()
                        ))
        
        except Exception as e:
            print(f"Network scan error: {e}")

    def run_discovery(self):
        """Run complete device discovery."""
        print("Starting Device Discovery and Health Check...")
        print("="*60)
        
        self.discover_hubitat()
        self.discover_weather_api()
        self.discover_govee_devices()
        self.scan_network_devices()
        
        print("\n" + "="*60)
        print("DISCOVERY RESULTS")
        print("="*60)
        
        online_count = 0
        error_count = 0
        offline_count = 0
        
        for device in self.devices:
            status_emoji = {
                "online": "[OK]",
                "offline": "[OFFLINE]",
                "error": "[ERROR]",
                "unknown": "[UNKNOWN]"
            }.get(device.status, "[UNKNOWN]")
            
            print(f"\n{status_emoji} {device.name} ({device.type})")
            print(f"   Address: {device.address}")
            if device.port:
                print(f"   Port: {device.port}")
            print(f"   Status: {device.status.upper()}")
            
            if device.status == "online":
                online_count += 1
            elif device.status == "error":
                error_count += 1
            elif device.status == "offline":
                offline_count += 1
            
            # Show key details
            if "error" in device.details:
                print(f"   WARNING: {device.details['error']}")
            elif device.status == "online":
                if device.type == "hub" and "device_count" in device.details:
                    print(f"   Devices: {device.details['device_count']}")
                elif device.type == "sensor":
                    if "temperature" in device.details and device.details["temperature"]:
                        print(f"   Temperature: {device.details['temperature']}°F")
                    if "humidity" in device.details and device.details["humidity"]:
                        print(f"   Humidity: {device.details['humidity']}%")
                elif device.type == "external_api":
                    if "current_temp" in device.details:
                        print(f"   Current Weather: {device.details['current_temp']}°F")
        
        print(f"\n" + "="*60)
        print("SUMMARY")
        print(f"Online: {online_count}")
        print(f"Offline: {offline_count}") 
        print(f"Errors: {error_count}")
        print(f"Total Devices: {len(self.devices)}")
        
        # Provide recommendations
        print(f"\n" + "="*60)
        print("RECOMMENDATIONS")
        
        if error_count > 0:
            print("Fix configuration errors:")
            for device in self.devices:
                if device.status == "error" and "error" in device.details:
                    print(f"   - {device.name}: {device.details['error']}")
        
        if offline_count > 0:
            print("Power on offline devices:")
            for device in self.devices:
                if device.status == "offline":
                    print(f"   - {device.name} ({device.address})")
        
        if online_count > 0:
            print("Ready for integration:")
            for device in self.devices:
                if device.status == "online":
                    print(f"   - {device.name}")
        
        print(f"\n" + "="*60)
        print("Next steps:")
        print("1. Power on any offline devices")
        print("2. Fix any configuration errors")
        print("3. Verify API credentials are current")
        print("4. Run this script again to confirm all devices are online")
        print("5. Proceed with service integration")
        
        return self.devices

if __name__ == "__main__":
    discovery = DeviceDiscovery()
    discovery.run_discovery()