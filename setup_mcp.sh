#!/bin/bash
# DevOps Center MCP Server Setup Script
# Запуск: bash /opt/projects/devops-center/setup_mcp.sh

set -e

echo "=== DevOps Center MCP Server Setup ==="

# 1. Git pull
cd /opt/projects/devops-center
git pull
echo "✓ Code updated"

# 2. Install Python deps
pip3 install 'mcp[cli]' requests --break-system-packages -q
echo "✓ Dependencies installed"

# 3. Open port
iptables -I INPUT -p tcp --dport 8001 -j ACCEPT 2>/dev/null || true
echo "✓ Port 8001 opened"

# 4. Create systemd service
cat > /etc/systemd/system/devops-mcp.service << 'EOF'
[Unit]
Description=DevOps Center MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/projects/devops-center
Environment=DEVOPS_API_URL=http://localhost:8000
Environment=DEVOPS_API_KEY=devops-2match-secret-2026
Environment=MCP_HOST=0.0.0.0
Environment=MCP_PORT=8001
ExecStart=/usr/bin/python3 /opt/projects/devops-center/mcp_server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Service file created"

# 5. Enable and start
systemctl daemon-reload
systemctl enable devops-mcp
systemctl restart devops-mcp
sleep 4

# 6. Check status
systemctl status devops-mcp --no-pager -l
echo ""
echo "=== Testing MCP endpoint ==="
curl -s --max-time 5 http://localhost:8001/mcp || echo "MCP server starting (may take a moment)"
echo ""
echo "=== Done! ==="
echo "MCP Server: http://87.199.198.120:8001/mcp"
