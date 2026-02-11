# SSH Setup Guide for Multi-Station Control

This guide explains how to set up passwordless SSH access from Pi 2 (master) to all other stations.

## Prerequisites

- All Pis must be connected to the same network
- You must know the hostname or IP of each Pi
- Default hostnames: `pi-controller-02.local`, `pi-controller-03.local`, etc.

## Step 1: Generate SSH Key on Pi 2 (Master)

On Pi 2, generate an SSH key if you don't have one:

```bash
ssh-keygen -t rsa -b 4096 -C "pi2-master"
```

When prompted:
- Press Enter to accept default location (`~/.ssh/id_rsa`)
- Press Enter twice for no passphrase (required for passwordless login)

## Step 2: Copy SSH Key to Each Station

Copy your SSH public key to each station (Pi 3-11):

```bash
# For each station, run:
ssh-copy-id pi@pi-controller-03.local
ssh-copy-id pi@pi-controller-04.local
ssh-copy-id pi@pi-controller-05.local
ssh-copy-id pi@pi-controller-06.local
ssh-copy-id pi@pi-controller-07.local
ssh-copy-id pi@pi-controller-08.local
ssh-copy-id pi@pi-controller-09.local
ssh-copy-id pi@pi-controller-10.local
ssh-copy-id pi@pi-controller-11.local
```

You'll be prompted for the password once per station.

## Step 3: Test SSH Access

Test that you can SSH without a password:

```bash
ssh pi@pi-controller-03.local "echo 'Connection successful'"
```

If successful, you should see "Connection successful" without entering a password.

## Step 4: Update keyboard.py Configuration

Edit `keyboard.py` and update these values if needed:

```python
# Path to main.py on remote Pis
REMOTE_MAIN_PATH = "/home/pi/Oriental_CvD_Controller_Murata/main.py"

# Python command (use full path if using venv)
REMOTE_PYTHON = "python3"
# Or for virtual environment:
# REMOTE_PYTHON = "/home/pi/Oriental_CvD_Controller_Murata/venv/bin/python"

# User and hostname for each station
STATIONS = {
    "02": {"host": "pi-controller-02.local", "port": 9000, "user": "pi"},
    ...
}
```

## Step 5: Clone Repository on All Stations

Ensure the code repository exists on all stations:

```bash
# On each Pi (or SSH from Pi 2):
cd /home/pi
git clone <your-repo-url> Oriental_CvD_Controller_Murata
cd Oriental_CvD_Controller_Murata

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 6: Configure Each Station

On each station, create `config/local.json`:

```bash
# On Pi 2:
echo '{"station_id": "02"}' > config/local.json

# On Pi 3:
echo '{"station_id": "03"}' > config/local.json

# ... and so on for each station
```

## Usage

Once SSH is set up, start the system:

### On Pi 2 (Master):

```bash
cd /home/pi/Oriental_CvD_Controller_Murata
python keyboard.py
```

### Control Flow:

1. **Press V key (first time)**: SSH into all stations and start `main.py`
   - All stations will auto-initialize (homing)
   - Wait ~30-60 seconds for homing to complete

2. **Press V key (second time)**: Start operations
   - All motors start moving
   - Videos start playing
   - Auto-loop continues after each cycle

3. **Press V key (while running)**: Stop operations
   - Stations 5,6,7,8,9: Return to position 0
   - Stations 2,3,4,10: Stop in place

4. **Press V key (after stopped)**: Resume operations

## Troubleshooting

### SSH Connection Refused

```bash
# Check if SSH is enabled on target Pi
sudo systemctl status ssh

# Enable SSH if needed
sudo systemctl enable ssh
sudo systemctl start ssh
```

### SSH Timeout or Host Not Found

```bash
# Check if Pi is reachable
ping pi-controller-03.local

# If .local doesn't work, use IP address
ping 192.168.1.103
```

### Permission Denied

```bash
# Verify SSH key was copied correctly
ssh-copy-id pi@pi-controller-03.local

# Test connection
ssh pi@pi-controller-03.local "whoami"
```

### Main.py Not Found

```bash
# Check path on remote Pi
ssh pi@pi-controller-03.local "ls -la /home/pi/Oriental_CvD_Controller_Murata/main.py"

# Update REMOTE_MAIN_PATH in keyboard.py if path is different
```

### Python Virtual Environment Issues

If using venv, update `keyboard.py`:

```python
REMOTE_PYTHON = "/home/pi/Oriental_CvD_Controller_Murata/venv/bin/python"
```

## Stopping All Stations

To stop all running main.py processes:

```bash
# From Pi 2, run for each station:
ssh pi@pi-controller-03.local "pkill -f main.py"
ssh pi@pi-controller-04.local "pkill -f main.py"
# ... etc

# Or create a stop script
```

## Auto-Start on Pi Boot (Optional)

To make each Pi auto-start when powered on, create a systemd service:

```bash
# On each Pi, create /etc/systemd/system/motor-controller.service
sudo nano /etc/systemd/system/motor-controller.service
```

Content:
```ini
[Unit]
Description=Oriental Motor Controller
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Oriental_CvD_Controller_Murata
ExecStart=/home/pi/Oriental_CvD_Controller_Murata/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable motor-controller
sudo systemctl start motor-controller

# Check status
sudo systemctl status motor-controller

# View logs
journalctl -u motor-controller -f
```
