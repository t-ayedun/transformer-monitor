# File Manifest: What Does Everything Do?

A component-by-component breakdown of the project.

> [!NOTE]
> **Necessity Rating:**
> - **CRITICAL**: The system will not run without this.
> - **IMPORTANT**: System runs, but loses major features (e.g., WiFi, storage management).
> - **OPTIONAL**: Can be safely ignored if you don't use that specific feature (e.g., FTP, Web UI).

## 1. Core System (`src/`)

These files form the "brain" of the monitoring system.

| File | Purpose | Necessity |
|------|---------|-----------|
| **`main.py`** | **The Commander**. Initializes everything and runs the main loop. | **CRITICAL** |
| **`config_manager.py`** | Loads settings from YAML files and Environment Variables. | **CRITICAL** |
| **`thermal_capture.py`** | Drivers for the MLX90640. Handles bad pixels, denoising, and Pi 5 fixes. | **CRITICAL** |
| **`smart_camera.py`** | Controls the Pi Camera. Handles motion detection and video recording. | **CRITICAL** |
| **`aws_publisher.py`** | Sends data to AWS IoT Core. Handles offline buffering and retries. | **CRITICAL** |
| **`storage_manager.py`** | **Janitor**. Deletes old files to prevent SD card from filling up. | **CRITICAL** |
| **`local_buffer.py`** | SQLite database wrapper. Saves data when internet is down. | **CRITICAL** |
| **`watchdog.py`** | **Safety Switch**. Restarts the app if it hangs/freezes. | **IMPORTANT** |
| **`network_monitor.py`** | Checks internet connectivity to pause/resume AWS uploads. | **IMPORTANT** |

### Feature Modules
| File | Purpose | Necessity |
|------|---------|-----------|
| `camera_web_interface.py` | Runs the local website (port 5000) for live streaming. | **OPTIONAL** (Disable in config) |
| `ftp_cold_storage.py` | Uploads old bulk data to FTP server. | **OPTIONAL** (Disable in config) |
| `ftp_publisher.py` | Helper for FTP uploads. | **OPTIONAL** |
| `heartbeat.py` | Sends "I'm alive" signals to AWS every 5 mins. | **IMPORTANT** (For monitoring uptime) |
| `event_classifier.py` | AI logic to decide if motion is a "Person" or "Animal". | **IMPORTANT** (Reduces false alerts) |
| `data_processor.py` | Math logic for ROI stats (min/max/avg temps). | **CRITICAL** |
| `roi_mapper.py` | Helper for defining Regions of Interest. | **CRITICAL** |
| `error_recovery.py` | Advanced self-healing logic for camera crashes. | **IMPORTANT** |
| `event_logger.py` | Structured logging for significant events. | **IMPORTANT** |

## 2. Scripts (`scripts/`)

Helpers for setup and deployment.

| File | Purpose | Necessity |
|------|---------|-----------|
| **`start.sh`** | **Entrypoint**. The script that actually runs `main.py`. Sets up env. | **CRITICAL** |
| **`generate_config.py`** | **Auto-Configurator**. Reads `.env` and writes YAML config files. | **CRITICAL** (for automation) |
| `setup_pi.sh` | One-time setup script for new Pis (installs libraries). | **IMPORTANT** (For new installs) |
| `install_autostart.sh` | Installs the systemd service. | **IMPORTANT** (For auto-start) |
| `transformer-monitor.service` | The systemd configuration file. | **IMPORTANT** (For auto-start) |
| `calibration.py` | Tool to calibrate thermal camera offsets. | **OPTIONAL** (Run manually) |
| `diagnose_thermal_pi5.py` | Debug tool specifically for Pi 5 I2C issues. | **OPTIONAL** (Debug only) |
| `deploy.sh` | Legacy deployment helper. | **OPTIONAL** |
| `test_integration.py` | Quick test to see if hardware works. | **OPTIONAL** (Debug only) |

## 3. Tests (`tests/`)

Unit tests to ensure code quality. **None of these are needed for the live system to run.**

| File | Purpose | Necessity |
|------|---------|-----------|
| `test_*.py` | Verified logic integrity during development. | **DEV ONLY** |

## Summary
- **Keep everything in `src/`**. Even "Optional" files are imported by `main.py` and strictly controlled via `site_config.yaml`. Deleting them will cause `ImportError`.
- **Scripts**: You mainly need `start.sh`, `generate_config.py`, and `install_autostart.sh`. The rest are helpful tools.
- **Tests**: Safe to ignore on the production device, but good to keep for reference.
