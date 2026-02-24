# Systemd Auto-Start Installation Guide

This guide shows how to set up main.py to automatically start on boot using systemd.

## Installation Steps

### 1. Copy the service file to systemd directory

```bash
sudo cp motor-controller.service /etc/systemd/system/
```

### 2. Reload systemd to recognize the new service

```bash
sudo systemctl daemon-reload
```

### 3. Enable the service to start on boot

```bash
sudo systemctl enable motor-controller.service
```

### 4. Start the service now (without rebooting)

```bash
sudo systemctl start motor-controller.service
```

## Service Management Commands

### Check service status
```bash
sudo systemctl status motor-controller.service
```

### View service logs
```bash
sudo journalctl -u motor-controller.service -f
```

### Stop the service
```bash
sudo systemctl stop motor-controller.service
```

### Restart the service
```bash
sudo systemctl restart motor-controller.service
```

### Disable auto-start on boot
```bash
sudo systemctl disable motor-controller.service
```

## Verify Installation

After installation, the service should:
1. Start automatically when the Pi boots
2. Connect to the motor via Modbus
3. Perform homing (if configured)
4. Listen for OSC commands on port 9010

Check the logs to verify:
```bash
sudo journalctl -u motor-controller.service -n 50
```

You should see output like:
```
Oriental Motor CVD Controller - Station 05
Motor driver connected
Starting automatic homing...
Homing complete - Motor READY
OSC listener started on port 9010
```

## Troubleshooting

### Service fails to start
- Check the paths in motor-controller.service match your installation
- Verify Python virtual environment exists at `/home/pi/Oriental_CvD_Controller_Murata/venv`
- Check permissions: `ls -l /home/pi/Oriental_CvD_Controller_Murata/main.py`

### Can't see logs
```bash
# View all logs
sudo journalctl -u motor-controller.service

# Follow logs in real-time
sudo journalctl -u motor-controller.service -f

# View last 100 lines
sudo journalctl -u motor-controller.service -n 100
```

### Service crashes and restarts
- The service is configured to automatically restart (RestartSec=10)
- Check logs to identify the crash reason
- Fix the issue and restart: `sudo systemctl restart motor-controller.service`

## Manual Start (without systemd)

If you prefer to start manually:

```bash
cd /home/pi/Oriental_CvD_Controller_Murata
source venv/bin/activate
python main.py
```
