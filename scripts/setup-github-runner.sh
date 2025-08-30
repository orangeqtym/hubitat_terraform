#!/bin/bash

# GitHub Self-Hosted Runner Setup Script
# Run this script on your local server to set up GitHub Actions runner

set -e

echo "🚀 Setting up GitHub Actions Self-Hosted Runner"
echo "=============================================="

# Check if running as root (recommended for system-wide runner)
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Running as root. Runner will be installed system-wide."
    INSTALL_DIR="/opt/actions-runner"
    SERVICE_USER="actions"
else
    echo "👤 Running as user. Runner will be installed in home directory."
    INSTALL_DIR="$HOME/actions-runner"
    SERVICE_USER="$USER"
fi

# Check prerequisites
echo "🔍 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
else
    echo "✅ Docker is installed"
fi

# Check curl
if ! command -v curl &> /dev/null; then
    echo "❌ curl is not installed. Please install curl first."
    exit 1
else
    echo "✅ curl is available"
fi

# Check for required environment files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔧 Checking environment files..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "✅ .env exists (consolidated configuration)"
else
    echo "❌ Missing environment file: .env"
    echo "   Please create .env file with all required environment variables"
    echo "   You can copy from .env.template and fill in your values"
    exit 1
fi

# Create actions user if running as root
if [ "$EUID" -eq 0 ] && ! id "$SERVICE_USER" &>/dev/null; then
    echo "👤 Creating actions user..."
    useradd -m -d /home/actions -s /bin/bash actions
    usermod -aG docker actions
fi

# Create installation directory
echo "📁 Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Download the latest runner if not already present
if [ ! -f "./run.sh" ]; then
    echo "⬇️  Downloading GitHub Actions Runner..."
    
    # Get the latest version
    RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep tag_name | cut -d '"' -f 4 | sed 's/v//')
    echo "Latest runner version: $RUNNER_VERSION"
    
    # Detect architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            RUNNER_ARCH="x64"
            ;;
        aarch64|arm64)
            RUNNER_ARCH="arm64"
            ;;
        *)
            echo "❌ Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
    
    # Download and extract
    curl -O -L "https://github.com/actions/runner/releases/download/v$RUNNER_VERSION/actions-runner-linux-$RUNNER_ARCH-$RUNNER_VERSION.tar.gz"
    tar xzf "./actions-runner-linux-$RUNNER_ARCH-$RUNNER_VERSION.tar.gz"
    rm "./actions-runner-linux-$RUNNER_ARCH-$RUNNER_VERSION.tar.gz"
    
    echo "✅ Runner downloaded and extracted"
fi

# Set permissions
if [ "$EUID" -eq 0 ]; then
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
fi

echo ""
echo "🔗 GitHub Runner Configuration"
echo "=============================="
echo ""
echo "To complete the setup, you need to configure the runner with your GitHub repository."
echo ""
echo "1. Go to your GitHub repository settings:"
echo "   https://github.com/YOUR_USERNAME/hubitat_terraform/settings/actions/runners"
echo ""
echo "2. Click 'New self-hosted runner'"
echo "3. Select Linux as the operating system"
echo "4. Follow the configuration commands, but use this directory: $INSTALL_DIR"
echo ""
echo "Example configuration command:"
echo "./config.sh --url https://github.com/YOUR_USERNAME/hubitat_terraform --token YOUR_TOKEN"
echo ""
echo "5. After configuration, install and start the service:"
if [ "$EUID" -eq 0 ]; then
    echo "sudo ./svc.sh install $SERVICE_USER"
    echo "sudo ./svc.sh start"
else
    echo "./run.sh"
    echo "(Or set up as a systemd service manually)"
fi
echo ""
echo "📋 Runner will be installed at: $INSTALL_DIR"
echo "🔧 Service user: $SERVICE_USER"
echo ""
echo "✅ Prerequisites check completed!"
echo "   Continue with the GitHub configuration steps above."

# Test Docker access for the service user
echo ""
echo "🧪 Testing Docker access..."
if [ "$EUID" -eq 0 ]; then
    if sudo -u "$SERVICE_USER" docker ps &>/dev/null; then
        echo "✅ Docker access confirmed for $SERVICE_USER"
    else
        echo "⚠️  Docker access issue for $SERVICE_USER. Adding to docker group..."
        usermod -aG docker "$SERVICE_USER"
        echo "   Please restart your server for group changes to take effect"
    fi
else
    if docker ps &>/dev/null; then
        echo "✅ Docker access confirmed for $USER"
    else
        echo "⚠️  Docker access issue. Please ensure $USER is in the docker group:"
        echo "   sudo usermod -aG docker $USER"
        echo "   Then log out and log back in"
    fi
fi