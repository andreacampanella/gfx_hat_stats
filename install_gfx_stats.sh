#!/bin/bash
# Installation script for GFX HAT System Stats Display

echo "Installing GFX HAT System Stats Display..."

# Install required Python packages
echo "Installing Python dependencies..."
pip3 install --user psutil Pillow

# Install GFX HAT library if not already installed
if ! python3 -c "import gfxhat" 2>/dev/null; then
    echo "GFX HAT library not found. Installing..."
    curl -sS https://get.pimoroni.com/gfxhat | bash
    echo "Please reboot after installation completes, then run this script again."
    exit 0
fi

# Copy the Python script
echo "Copying script to /home/dietpi..."
cp gfx_hat_stats.py /home/dietpi/
chmod +x /home/dietpi/gfx_hat_stats.py

# Install systemd service
echo "Installing systemd service..."
sudo cp gfx-hat-stats.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gfx-hat-stats.service
sudo systemctl start gfx-hat-stats.service

echo ""
echo "Installation complete!"
echo ""
echo "The display will show 3 pages:"
echo "  Page 1: IP address and Copyparty status"
echo "  Page 2: CPU usage, temperature, and RAM"
echo "  Page 3: Storage usage (/mnt/storage)"
echo ""
echo "Use the capacitive touch buttons to navigate:"
echo "  Button A (leftmost): Previous page"
echo "  Button B: Next page"
echo "  Button C: Next page"
echo ""
echo "Service status:"
sudo systemctl status gfx-hat-stats.service --no-pager
echo ""
echo "To view logs: sudo journalctl -u gfx-hat-stats -f"
echo "To stop: sudo systemctl stop gfx-hat-stats"
echo "To restart: sudo systemctl restart gfx-hat-stats"
