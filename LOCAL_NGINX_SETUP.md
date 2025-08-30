# Local Nginx Proxy Setup (Clean URLs without Ports)

This setup is **local only** and not tracked in git. It provides clean URLs like `http://iot.matilda.local/` instead of `http://matilda.local:8014/`.

## 1. Install Nginx

```bash
sudo apt update
sudo apt install nginx
```

## 2. Create Site Configuration

```bash
sudo nano /etc/nginx/sites-available/local-services
```

Add this configuration:

```nginx
# IoT Dashboard - main entry point
server {
    listen 80;
    server_name iot.matilda.local;

    location / {
        proxy_pass http://localhost:8014;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Weather API
server {
    listen 80;
    server_name weather.matilda.local;

    location / {
        proxy_pass http://localhost:8011;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Hubitat Hub
server {
    listen 80;
    server_name hubitat.matilda.local;

    location / {
        proxy_pass http://localhost:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Govee Sensors
server {
    listen 80;
    server_name govee.matilda.local;

    location / {
        proxy_pass http://localhost:8012;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Database API
server {
    listen 80;
    server_name database.matilda.local;

    location / {
        proxy_pass http://localhost:8013;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 3. Enable the Site

```bash
# Enable the configuration
sudo ln -s /etc/nginx/sites-available/local-services /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

## 4. Update Avahi for Subdomains

```bash
sudo nano /etc/avahi/services/iot-subdomains.service
```

Add:

```xml
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name>IoT Services</name>
  <service>
    <type>_http._tcp</type>
    <port>80</port>
    <host-name>iot.matilda.local</host-name>
  </service>
  <service>
    <type>_http._tcp</type>
    <port>80</port>
    <host-name>weather.matilda.local</host-name>
  </service>
  <service>
    <type>_http._tcp</type>
    <port>80</port>
    <host-name>hubitat.matilda.local</host-name>
  </service>
  <service>
    <type>_http._tcp</type>
    <port>80</port>
    <host-name>govee.matilda.local</host-name>
  </service>
  <service>
    <type>_http._tcp</type>
    <port>80</port>
    <host-name>database.matilda.local</host-name>
  </service>
</service-group>
```

Restart Avahi:
```bash
sudo systemctl restart avahi-daemon
```

## 5. Test Clean URLs

From your laptop, you can now access:

- **IoT Dashboard**: `http://iot.matilda.local/`
- **Weather API**: `http://weather.matilda.local/`
- **Hubitat Hub**: `http://hubitat.matilda.local/`
- **Govee Sensors**: `http://govee.matilda.local/`
- **Database API**: `http://database.matilda.local/`

**No ports needed!** 🎉

## Troubleshooting

- Check nginx status: `sudo systemctl status nginx`
- View nginx logs: `sudo journalctl -u nginx -f`
- Test subdomain resolution: `ping iot.matilda.local`