# Configuration Guide

## Quick Setup for Each Raspberry Pi

Each Raspberry Pi needs **only one file** to configure which station it is.

### Step 1: Create `local.json` on each Pi

On **pi-controller-02**:
```json
{
  "station_id": "02"
}
```

On **pi-controller-06**:
```json
{
  "station_id": "06"
}
```

On **pi-controller-prologue**:
```json
{
  "station_id": "prologue"
}
```

### Step 2: Enable network master on the Pi with USB keyboard (optional)

If you have a USB keyboard connected to one Pi (e.g., station 02), edit `network_master.json`:

```json
{
  "enabled": true,
  "keyboard": {
    "enabled": true,
    "type": "usb",
    "keys": {
      "start_stop": "v",
      "standby": "c",
      "emergency": "ctrl"
    }
  }
}
```

**Keyboard Controls:**
- **V key**: Toggle start/stop operation
- **C key**: Enter standby mode (motors return home)
- **Ctrl key**: Clear motor alarm

**On all other Pis**, set:
```json
{
  "enabled": false
}
```

Or just delete `network_master.json` on slave stations.

### Step 3: Run

On each Pi, just run:
```bash
python3 main.py
```

No command-line arguments needed! The Pi reads `local.json` to know which station it is.

---

## File Structure

```
config/
├── local.json              # Which station am I? (different on each Pi)
├── network_master.json     # Am I the keyboard master? (only on master Pi)
└── all_stations.json       # All station configs (same on all Pis)
```

### Benefits of this architecture:

1. **Same code on all Pis** - Just pull from git
2. **One file to configure** - Only change `local.json` per Pi
3. **Keyboard can be anywhere** - Not tied to station 02
4. **Network master separate** - Station number ≠ master controller
5. **Clean and simple** - No command-line arguments needed

---

## Example Deployment

**On pi-controller-02** (with keyboard):
```bash
cd /home/user/Desktop/hihi/Oriental_CvD_Controller_Murata
git pull

# Create local.json
echo '{"station_id": "02"}' > config/local.json

# Enable as master
cat > config/network_master.json << 'EOF'
{
  "enabled": true,
  "target_stations": ["prologue", "02", "03", "04", "05", "06", "07", "08", "09", "10", "epilogue"],
  "keyboard": {
    "enabled": true,
    "type": "usb",
    "keys": {
      "start_stop": "v",
      "standby": "c",
      "emergency": "ctrl"
    }
  }
}
EOF

python3 main.py
```

**On pi-controller-06** (slave):
```bash
cd /home/user/Desktop/hihi/Oriental_CvD_Controller_Murata
git pull

# Create local.json
echo '{"station_id": "06"}' > config/local.json

# Disable master (or delete the file)
echo '{"enabled": false}' > config/network_master.json

python3 main.py
```

Done!
