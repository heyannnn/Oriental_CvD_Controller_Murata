# Deployment Guide

## Architecture Overview

**Same Python code runs on ALL 11 Raspberry Pis. Only the config file changes!**

```
Oriental_CvD_Controller_Murata/   ← Same code on ALL Pis
├── main.py                       ← Universal entry point
├── services/                     ← Shared code
├── drivers/                      ← Shared code
├── config/                       ← Station-specific configs
│   ├── station_prologue.json     ← Pi-Prologue
│   ├── station_02.json           ← Pi-02 (Master with keyboard)
│   ├── station_03.json           ← Pi-03
│   ├── ...                       ← Pi-04 through Pi-10
│   └── station_epilogue.json     ← Pi-Epilogue (video only)
└── tests/                        ← Diagnostic tools
```

---

## Quick Start

### On Each Raspberry Pi:

```bash
# 1. Clone repo (one time)
cd ~
git clone https://github.com/heyannnn/Oriental_CvD_Controller_Murata.git
cd Oriental_CvD_Controller_Murata

# 2. Install dependencies (one time)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Run with station-specific config
python main.py --station 02      # For Pi-02
python main.py --station 06      # For Pi-06
python main.py --station epilogue  # For Pi-Epilogue
```

---

## Station Configuration Map

| Pi Hostname | Station ID | Config File | Motors | Keyboard | LED |
|-------------|------------|-------------|--------|----------|-----|
| pi-controller-prologue | `prologue` | station_prologue.json | 1 | No | No |
| pi-controller-02 | `02` | station_02.json | 1 | **Yes** | No |
| pi-controller-03 | `03` | station_03.json | 1 | No | No |
| pi-controller-04 | `04` | station_04.json | **3** | No | No |
| pi-controller-05 | `05` | station_05.json | 1 | No | No |
| pi-controller-06 | `06` | station_06.json | 1 | No | No |
| pi-controller-07 | `07` | station_07.json | 1 | No | **Yes** |
| pi-controller-08 | `08` | station_08.json | 2 | No | No |
| pi-controller-09 | `09` | station_09.json | 2 | No | No |
| pi-controller-10 | `10` | station_10.json | 1 | No | **Yes** |
| pi-controller-11 | `11` | station_epilogue.json | **0** | No | No |

---

## How It Works

### 1. Same Code Everywhere
```bash
# All Pis run the same main.py
python main.py --station XX
```

### 2. Config Defines Behavior
The `--station` argument loads the corresponding JSON file:
- `--station 02` → loads `config/station_02.json`
- `--station 06` → loads `config/station_06.json`
- `--station epilogue` → loads `config/station_epilogue.json`

### 3. Config File Contents
Each config file defines:
```json
{
  "station_id": "06",
  "station_name": "工程6",

  "serial": {
    "port": "/dev/ttyUSB0",
    "baudrate": 230400,
    "parity": "N",
    "stopbits": 1
  },

  "motors": [                    // Empty array = no motors
    {
      "name": "motor_1",
      "slave_id": 1,
      "type": "CVD-28-KR"
    }
  ],

  "keyboard": {
    "enabled": false             // Only true for station 02
  },

  "network": {
    "listen_port": 9000,
    "send_port": 9001,
    "is_sender": false,          // Only true for station 02
    "video_player_ip": "127.0.0.1",
    "video_player_port": 9002
  }
}
```

---

## Deployment Steps

### Deploy to All Pis (One-Time Setup)

```bash
# On your Mac - create deploy script
cat > deploy_all.sh << 'EOF'
#!/bin/bash
for station in prologue 02 03 04 05 06 07 08 09 10 11; do
  if [ "$station" = "11" ]; then
    host="pi-controller-11.local"
    config="epilogue"
  else
    host="pi-controller-$station.local"
    config="$station"
  fi

  echo "=== Deploying to $host (station $config) ==="

  ssh user@$host << ENDSSH
    cd ~
    rm -rf Oriental_CvD_Controller_Murata
    git clone https://github.com/heyannnn/Oriental_CvD_Controller_Murata.git
    cd Oriental_CvD_Controller_Murata
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    echo "✓ Deployed station $config"
ENDSSH

done
EOF

chmod +x deploy_all.sh
./deploy_all.sh
```

### Update All Pis (After Code Changes)

```bash
# On your Mac - push code changes
git add .
git commit -m "Update motor control"
git push

# Update all Pis
for station in prologue 02 03 04 05 06 07 08 09 10 11; do
  if [ "$station" = "11" ]; then
    host="pi-controller-11.local"
  else
    host="pi-controller-$station.local"
  fi

  echo "Updating $host..."
  ssh user@$host "cd ~/Oriental_CvD_Controller_Murata && git pull"
done
```

---

## Systemd Service Setup

### On Each Pi:

```bash
# 1. Edit systemd service file
cd ~/Oriental_CvD_Controller_Murata
nano systemd/oriental-controller.service

# 2. Set STATION_ID environment variable
#    For Pi-02:
Environment="STATION_ID=02"

#    For Pi-06:
Environment="STATION_ID=06"

#    For Pi-Epilogue:
Environment="STATION_ID=epilogue"

# 3. Install service
sudo cp systemd/oriental-controller.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable oriental-controller
sudo systemctl start oriental-controller

# 4. Check status
sudo systemctl status oriental-controller
sudo journalctl -u oriental-controller -f
```

---

## Testing Individual Stations

### On Mac (Development):

```bash
# Test with any station config
python tests/test_keyboard_control.py  # Simple motor test

# Or simulate a specific station
python main.py --station 06  # Will fail (no GPIO) but shows config loading
```

### On Raspberry Pi:

```bash
cd ~/Oriental_CvD_Controller_Murata
source venv/bin/activate

# Test motor connection
python tests/test_cvd_basic.py

# Run the main program
python main.py --station 06

# Station 02 only (with keyboard):
python main.py --station 02
```

---

## Customizing Per Station

### To Change Serial Port (if not /dev/ttyUSB0):

Edit the specific station config file:
```bash
nano config/station_06.json

# Change:
"port": "/dev/ttyUSB1"
```

### To Add More Motors:

```json
"motors": [
  {
    "name": "motor_1",
    "slave_id": 1,
    "type": "CVD-28-KR"
  },
  {
    "name": "motor_2",
    "slave_id": 2,
    "type": "CVD-28-KR"
  }
]
```

### To Enable Keyboard (Station 02):

```json
"keyboard": {
  "enabled": true,
  "gpio": {
    "start_button": 17,
    "stop_button": 27,
    "reset_button": 22
  }
}
```

### To Enable LEDs (Stations 07, 10):

```json
"led": {
  "enabled": true,
  "gpio_pin": 18,
  "pixel_count": 60,
  "brightness": 128
}
```

---

## Troubleshooting

### "Config file not found"
```bash
# Make sure you're using correct station ID
python main.py --station 02   # ✓ Correct
python main.py --station 2    # ✗ Wrong (need leading zero)
python main.py --station epilogue  # ✓ Correct
```

### Motor Not Responding
```bash
# Run diagnostic
python tests/scan_slave_id.py

# Or comprehensive scan
python tests/scan_all_settings.py
```

### Check Which Config is Loaded
```bash
python main.py --station 06  # First log line shows config path
```

---

## Summary

✅ **Same code on all Pis**
✅ **Different behavior via config**
✅ **Easy to update (just git pull)**
✅ **Clean and beautiful** 🎨

To change a station's behavior: **Edit its config file, that's it!**
