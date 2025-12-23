# Vehicle Telemetry Monitor - Deployment Guide

## ✅ Quick Start (One-Time Setup)

### Option 1: Auto-Start via Task Scheduler (Recommended)

Run this in **PowerShell as Administrator**:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
C:\Users\peepu\Downloads\Moniter\setup_scheduler.ps1
```

This will:
- Register a scheduled task to start the server automatically on system startup
- Run with highest privileges
- Server will be accessible at `http://<your-ip>:8000` from any machine on your network

### Option 2: Manual Start

Double-click: `C:\Users\peepu\Downloads\Moniter\run_server.bat`

Or from CMD:
```batch
C:\Users\peepu\Downloads\Moniter\run_server.bat
```

---

## 🌐 Access from Other Machines

1. **Find your computer's IP address:**
   ```batch
   ipconfig
   ```
   Look for "IPv4 Address" (usually 192.168.x.x or 10.x.x.x)

2. **Open in browser:**
   ```
   http://<your-ip>:8000
   ```
   Example: `http://192.168.1.100:8000`

---

## 📋 What's Running

- ✅ **FastAPI** - REST + WebSocket backend
- ✅ **MQTT** - Connected to broker and receiving vehicle telemetry
- ✅ **Real-time Dashboard** - Live SOC %, speed, location, drive mode
- ✅ **Map Tracking** - OpenStreetMap with vehicle route

---

## 🛑 Stop the Server

- **Manual:** Close the batch script window or press `Ctrl+C`
- **Scheduler:** Right-click `VehicleMoniterServer` in Task Scheduler > Disable (to prevent auto-restart)

---

## 🔧 Manage Scheduled Task

### View Task Status
```powershell
Get-ScheduledTask -TaskName "VehicleMoniterServer"
```

### Disable Auto-Start
```powershell
Disable-ScheduledTask -TaskName "VehicleMoniterServer"
```

### Remove Task
```powershell
Unregister-ScheduledTask -TaskName "VehicleMoniterServer" -Confirm:$false
```

### Re-enable Auto-Start
```powershell
Enable-ScheduledTask -TaskName "VehicleMoniterServer"
```

---

## 📝 Configuration

- **Host:** `0.0.0.0` (all network interfaces)
- **Port:** `8000`
- **MQTT Broker:** `w8e06e1d.ala.asia-southeast1.emqxsl.com:8883`
- **Topic:** `vehicle/nandi_2/data`

To modify, edit: `C:\Users\peepu\Downloads\Moniter\app\main.py`

---

## ✨ Features

- **Live SOC Bar** - Color-coded (green/yellow/red)
- **Battery Energy** - Real-time kWh display
- **Speed & RPM** - Current vehicle metrics
- **Drive Mode** - Forward/Neutral/Reverse detection
- **Odometer** - Total distance traveled
- **Location Tracking** - Map with route history
- **Connection Status** - Shows WebSocket connection state

Enjoy! 🚀
