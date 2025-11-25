#!/usr/bin/env python3
"""
System Stats Display for Pimoroni GFX HAT
Page 1: IP, Copyparty status, Time/Date
Page 2: SD card space, NVMe storage, RAM usage
Page 3: CPU and Network usage graphs
Use - and + buttons to navigate pages
"""

import time
import socket
import psutil
import subprocess
from datetime import datetime
from collections import deque
from PIL import Image, ImageDraw, ImageFont

try:
    import gfxhat
    from gfxhat import touch, lcd, backlight, fonts
except ImportError:
    print("This script requires the gfxhat library")
    print("Install it with: curl -sS https://get.pimoroni.com/gfxhat | bash")
    exit(1)

# Display dimensions
WIDTH = 128
HEIGHT = 64

# Current page
current_page = 0
total_pages = 3

# Copyparty port
COPYPARTY_PORT = 8080

# Backlight color - White (adjust brightness by changing all values equally)
# Full brightness: (255, 255, 255)
# 75% brightness: (190, 190, 190)
# 50% brightness: (128, 128, 128)
# 25% brightness: (64, 64, 64)
# 10% brightness: (25, 25, 25)
BACKLIGHT_COLOR = (190, 190, 190)  # Dimmed white (25% brightness)

# Font size
FONT_SIZE = 12

# Graph data storage (keep last 64 points for full width)
cpu_history = deque([0] * WIDTH, maxlen=WIDTH)
net_history = deque([0] * WIDTH, maxlen=WIDTH)
last_net_io = None

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No network"

def is_copyparty_running():
    """Check if copyparty is running"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'copyparty'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.stdout.strip() == 'active':
            return True
        
        result = subprocess.run(
            ['pgrep', '-f', 'copyparty'],
            capture_output=True,
            text=True,
            timeout=2
        )
        return len(result.stdout.strip()) > 0
    except Exception:
        return False

def get_disk_usage(path):
    """Get disk usage for a path"""
    try:
        disk = psutil.disk_usage(path)
        return disk.percent, disk.used / (1024**3), disk.total / (1024**3)
    except Exception:
        return None, None, None

def get_memory_usage():
    """Get memory usage"""
    mem = psutil.virtual_memory()
    return mem.percent, mem.used / (1024**3), mem.total / (1024**3)

def get_cpu_temp():
    """Get CPU temperature"""
    try:
        temp = psutil.sensors_temperatures()
        if 'cpu_thermal' in temp:
            return temp['cpu_thermal'][0].current
        # Try reading directly from thermal zone
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return float(f.read()) / 1000.0
    except Exception:
        return None

def get_cpu_usage():
    """Get CPU usage percentage"""
    return psutil.cpu_percent(interval=0.1)

def get_network_usage():
    """Get network usage in KB/s"""
    global last_net_io
    
    try:
        net_io = psutil.net_io_counters()
        current_time = time.time()
        
        if last_net_io is not None:
            bytes_sent = net_io.bytes_sent - last_net_io['bytes_sent']
            bytes_recv = net_io.bytes_recv - last_net_io['bytes_recv']
            time_delta = current_time - last_net_io['time']
            
            if time_delta > 0:
                kb_per_sec = (bytes_sent + bytes_recv) / 1024 / time_delta
                last_net_io = {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'time': current_time
                }
                return kb_per_sec
        
        last_net_io = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'time': current_time
        }
        return 0
    except Exception:
        return 0

def set_backlight():
    """Set the backlight to white"""
    backlight.set_all(*BACKLIGHT_COLOR)
    backlight.show()

def draw_page_0(draw, font):
    """Page 1: IP, Copyparty status, Time/Date"""
    ip = get_local_ip()
    copyparty_status = is_copyparty_running()
    now = datetime.now()
    
    # IP address
    draw.text((2, 2), f"IP: {ip}", font=font, fill=1)
    
    # Copyparty status
    status = f"Port {COPYPARTY_PORT}" if copyparty_status else "Stopped"
    draw.text((2, 18), f"Copyparty: {status}", font=font, fill=1)
    
    # Time
    time_str = now.strftime("%H:%M:%S")
    draw.text((2, 34), time_str, font=font, fill=1)
    
    # Date
    date_str = now.strftime("%Y-%m-%d")
    draw.text((2, 50), date_str, font=font, fill=1)

def draw_page_1(draw, font):
    """Page 2: SD card, NVMe storage, RAM"""
    # SD Card (root filesystem)
    sd_pct, sd_used, sd_total = get_disk_usage('/')
    if sd_pct is not None:
        draw.text((2, 2), f"SD: {sd_pct:.0f}% ({sd_used:.1f}/{sd_total:.1f}GB)", font=font, fill=1)
    
    # NVMe Storage
    nvme_pct, nvme_used, nvme_total = get_disk_usage('/mnt/storage')
    if nvme_pct is not None:
        draw.text((2, 18), f"NVMe: {nvme_pct:.0f}%", font=font, fill=1)
        draw.text((2, 34), f"{nvme_used:.0f}/{nvme_total:.0f}GB", font=font, fill=1)
    else:
        draw.text((2, 18), "NVMe: N/A", font=font, fill=1)
    
    # RAM
    mem_pct, mem_used, mem_total = get_memory_usage()
    draw.text((2, 50), f"RAM: {mem_pct:.0f}% ({mem_used:.1f}/{mem_total:.1f}GB)", font=font, fill=1)

def draw_graph(draw, data, y_start, height, max_value=100):
    """Draw a horizontal graph"""
    if len(data) == 0:
        return
    
    # Draw graph border
    draw.rectangle([(0, y_start), (WIDTH-1, y_start + height - 1)], outline=1, fill=0)
    
    # Draw graph data
    for x, value in enumerate(data):
        if value > 0:
            # Scale value to graph height
            bar_height = int((value / max_value) * (height - 2))
            bar_height = min(bar_height, height - 2)
            if bar_height > 0:
                y_bottom = y_start + height - 2
                y_top = y_bottom - bar_height
                draw.line([(x + 1, y_top), (x + 1, y_bottom)], fill=1)

def draw_page_2(draw, font):
    """Page 3: CPU and Network graphs"""
    # Update graph data
    cpu_usage = get_cpu_usage()
    cpu_temp = get_cpu_temp()
    cpu_history.append(cpu_usage)
    
    net_usage = get_network_usage()
    # Scale network to reasonable range (0-1000 KB/s = 0-100%)
    net_scaled = min((net_usage / 1000) * 100, 100)
    net_history.append(net_scaled)
    
    # Small font for labels
    try:
        small_font = ImageFont.truetype(fonts.BitbuntuFull, 8)
    except Exception:
        small_font = font
    
    # CPU Graph (top half) - added spacing and temperature
    if cpu_temp:
        draw.text((2, 0), f"CPU {cpu_usage:.0f}% {cpu_temp:.0f}C", font=small_font, fill=1)
    else:
        draw.text((2, 0), f"CPU {cpu_usage:.0f}%", font=small_font, fill=1)
    draw_graph(draw, cpu_history, 12, 20)
    
    # Network Graph (bottom half) - added spacing
    draw.text((2, 34), f"NET {net_usage:.0f}KB/s", font=small_font, fill=1)
    draw_graph(draw, net_history, 46, 18)

def update_display():
    """Update the display with current page"""
    # Create image buffer
    image = Image.new('P', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    
    # Load font
    try:
        font = ImageFont.truetype(fonts.BitbuntuFull, FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()
    
    # Draw the current page
    if current_page == 0:
        draw_page_0(draw, font)
    elif current_page == 1:
        draw_page_1(draw, font)
    elif current_page == 2:
        draw_page_2(draw, font)
    
    # Convert image for display
    for x in range(WIDTH):
        for y in range(HEIGHT):
            pixel = image.getpixel((x, y))
            lcd.set_pixel(x, y, pixel)
    
    lcd.show()

def next_page(ch, event):
    """Go to next page"""
    global current_page
    if event == 'press':
        current_page = (current_page + 1) % total_pages
        update_display()

def prev_page(ch, event):
    """Go to previous page"""
    global current_page
    if event == 'press':
        current_page = (current_page - 1) % total_pages
        update_display()

def main():
    """Main loop"""
    print("GFX HAT System Stats Display")
    print("  - button: Previous page")
    print("  + button: Next page")
    print("Press Ctrl+C to exit")
    
    # Clear the display
    lcd.clear()
    lcd.show()
    
    # Set up button handlers
    touch.on(3, prev_page)    # - button
    touch.on(5, next_page)    # + button
    
    # Set backlight to white
    set_backlight()
    
    # Initial display
    update_display()
    
    try:
        # Update loop
        while True:
            update_display()
            time.sleep(2)  # Update every 2 seconds
    except KeyboardInterrupt:
        print("\nExiting...")
        lcd.clear()
        lcd.show()
        backlight.set_all(0, 0, 0)
        backlight.show()

if __name__ == "__main__":
    main()
