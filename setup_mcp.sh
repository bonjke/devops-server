#!/bin/bash
# DevOps Center MCP Server Setup Script

set -e
echo "=== DevOps Center MCP Server Setup ==="

cd /opt/projects/devops-center

# 1. Install Python deps (CentOS 10 compatible)
PIP=$(which pip3 2>/dev/null || which pip 2>/dev/null || echo "python3 -m pip")
echo "Using pip: $PIP"
$PIP install 'mcp[cli]' requests --break-system-packages -q 2>/dev/null || \
    python3 -m pip install 'mcp[cli]' requests -q
echo "✓ Dependencies installed"

# 2. Open port
iptables -I INPUT -p tcp --dport 8001 -j ACCEPT 2>/dev/null || true
echo "✓ Port 8001 opened"

# 3. Create systemd service
cat > /etc/systemd/system/devops-mcp.service << 'SVCEOF'
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
SVCEOF
echo "✓ Service file created"

# 4. Enable and start
systemctl daemon-reload
systemctl enable devops-mcp
systemctl restart devops-mcp
sleep 4

# 5. Status
systemctl status devops-mcp --no-pager -l

echo ""
echo "=== MCP Server: http://87.199.198.120:8001/mcp ==="
