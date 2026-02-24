#!/bin/bash
# EC2 Free Tier Setup Script for Healthcare Chatbot
# Run this on your EC2 t2.micro instance

set -e  # Exit on error

echo "🚀 Healthcare Chatbot - EC2 Free Tier Deployment"
echo "=================================================="

# 1. Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Install Docker
echo "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
    rm get-docker.sh
    echo "✅ Docker installed"
else
    echo "✅ Docker already installed"
fi

# 3. Install Docker Compose
echo "🔧 Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

# 4. Create swap file (CRITICAL for 1GB RAM)
echo "💾 Creating 4GB swap file..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # Make swap permanent
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    echo "✅ Swap created (4GB)"
else
    echo "✅ Swap already exists"
fi

# 5. Install nginx (optional)
echo "🌐 Installing Nginx..."
if ! command -v nginx &> /dev/null; then
    sudo apt install nginx -y
    echo "✅ Nginx installed"
else
    echo "✅ Nginx already installed"
fi

# 6. Clone repository
echo "📥 Cloning repository..."
if [ ! -d "deepblue-CMC-chatbot" ]; then
    git clone https://github.com/PratyushSowrirajan/deepblue-CMC-chatbot.git
    cd deepblue-CMC-chatbot
else
    echo "⚠️  Repository already exists. Pulling latest changes..."
    cd deepblue-CMC-chatbot
    git pull
fi

# 7. Setup environment
echo "🔐 Setting up environment..."
if [ ! -f .env ]; then
    read -p "Enter your CEREBRAS_API_KEY: " api_key
    echo "CEREBRAS_API_KEY=$api_key" > .env
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

# 8. Configure nginx
echo "⚙️  Configuring Nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/healthcare-chatbot > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass http://localhost:8000/health;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/healthcare-chatbot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
echo "✅ Nginx configured"

# 9. Build and run Docker container
echo "🏗️  Building Docker container..."
docker-compose down 2>/dev/null || true
docker-compose up -d --build

# 10. Setup auto-restart on reboot
echo "🔄 Setting up auto-restart on reboot..."
crontab -l 2>/dev/null | grep -v 'healthcare-chatbot' | { cat; echo "@reboot cd $(pwd) && /usr/local/bin/docker-compose up -d"; } | crontab -

# 11. Show status
echo ""
echo "✅ =================================================="
echo "✅ Deployment Complete!"
echo "✅ =================================================="
echo ""
echo "📋 Server Details:"
echo "   - API URL: http://$(curl -s http://checkip.amazonaws.com)"
echo "   - API Docs: http://$(curl -s http://checkip.amazonaws.com)/docs"
echo "   - Health: http://$(curl -s http://checkip.amazonaws.com)/health"
echo ""
echo "🔍 Useful Commands:"
echo "   - Check logs: docker-compose logs -f"
echo "   - Restart: docker-compose restart"
echo "   - Stop: docker-compose down"
echo "   - Check RAM: free -h"
echo "   - Check disk: df -h"
echo ""
echo "⏳ Note: First request may take 30-60 seconds (model loading)"
echo ""

# Test health endpoint
echo "🏥 Testing health endpoint..."
sleep 10
curl -f http://localhost:8000/health && echo "" && echo "✅ Server is healthy!" || echo "⚠️  Server not responding yet. Check logs: docker-compose logs"
