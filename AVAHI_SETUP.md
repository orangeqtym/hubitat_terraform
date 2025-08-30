# Avahi mDNS Setup

Run these commands once on your server to set up mDNS hostname resolution:

```bash
# Install Avahi daemon
sudo apt-get update
sudo apt-get install -y avahi-daemon avahi-utils

# Enable and start the service
sudo systemctl enable avahi-daemon
sudo systemctl start avahi-daemon

# Copy the service definition
sudo cp avahi/homeserver.service /etc/avahi/services/

# Restart to pick up the new service
sudo systemctl restart avahi-daemon

# Test mDNS resolution
avahi-resolve --name homeserver.local
```

After this setup, your server will be accessible as:
- `http://homeserver.local/` from any device on your network
- No more IP addresses or port numbers needed!

## Troubleshooting

If mDNS doesn't work:
1. Check firewall allows mDNS (port 5353 UDP)
2. Ensure avahi-daemon is running: `sudo systemctl status avahi-daemon`
3. Test with: `ping homeserver.local`