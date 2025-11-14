# Transformer Monitor - Production Deployment Plan

## Executive Summary

This document outlines the plan to transition the Transformer Thermal Monitor from test mode to production deployment across multiple sites with full AWS IoT MQTT integration and FTP data logging.

**Current Status**: ✅ Test Mode - Local operation confirmed working
**Target Status**: 🎯 Production Ready - Multi-site deployment with cloud data pipeline

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Architecture Overview](#2-architecture-overview)
3. [Deployment Phases](#3-deployment-phases)
4. [Implementation Tasks](#4-implementation-tasks)
5. [Testing Strategy](#5-testing-strategy)
6. [Deployment Procedures](#6-deployment-procedures)
7. [Monitoring & Maintenance](#7-monitoring--maintenance)
8. [Security Considerations](#8-security-considerations)

---

## 1. Current State Assessment

### ✅ Completed Components

**Core Functionality**:
- ✅ MLX90640 thermal camera integration (4Hz, I2C 100kHz)
- ✅ Pi Camera 3 visual monitoring with motion detection
- ✅ ROI mapper with drag-to-select and edit capabilities
- ✅ Dashboard with live thermal stream and ROI overlays
- ✅ DataProcessor for thermal analysis (min/max/avg per ROI)
- ✅ Local SQLite buffer for offline resilience
- ✅ Circular buffer video recording (pre/post motion)
- ✅ Flask web interface (port 5000)

**AWS/Cloud Components** (exist but not activated):
- ✅ `aws_publisher.py` - Full MQTT client with:
  - Exponential backoff retry
  - Data compression (gzip)
  - Network monitoring
  - Offline queue management
  - S3 image upload
  - Bandwidth throttling
- ✅ `ftp_publisher.py` - FTP client for data logging
- ✅ AWS config templates with environment variable substitution
- ✅ Certificate path configuration

**Infrastructure**:
- ✅ Docker containerization
- ✅ Systemd service support
- ✅ Watchdog timer for reliability
- ✅ Network monitor
- ✅ Storage manager
- ✅ Heartbeat monitor

### 🔧 Needs Implementation

**Integration Layer**:
- ⚠️ Connect AWS publisher to main.py data pipeline
- ⚠️ Connect FTP publisher to main.py data pipeline
- ⚠️ Thermal image serialization for transmission
- ⚠️ Video file upload pipeline
- ⚠️ Snapshot upload pipeline

**Configuration**:
- ⚠️ Production mode flag (disable TEST MODE)
- ⚠️ Multi-site configuration management
- ⚠️ Certificate provisioning script
- ⚠️ Environment-specific configs (dev/staging/prod)

**Deployment**:
- ⚠️ Site provisioning script
- ⚠️ Certificate installer
- ⚠️ Health check endpoints
- ⚠️ Deployment validation tests
- ⚠️ Update/rollback procedures

**Monitoring**:
- ⚠️ CloudWatch metrics integration
- ⚠️ Alert rules and notifications
- ⚠️ Performance monitoring dashboard

---

## 2. Architecture Overview

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RASPBERRY PI (SITE)                       │
│                                                              │
│  ┌──────────────┐        ┌──────────────┐                   │
│  │   MLX90640   │───────▶│   Thermal    │                   │
│  │Thermal Camera│  I2C   │   Capture    │                   │
│  └──────────────┘        └──────┬───────┘                   │
│                                 │                            │
│  ┌──────────────┐        ┌─────▼────────┐                   │
│  │ Pi Camera 3  │───────▶│    Data      │                   │
│  │Visual+Motion │        │  Processor   │                   │
│  └──────────────┘        └─────┬────────┘                   │
│                                 │                            │
│                          ┌──────▼───────┐                    │
│                          │ Local Buffer │                    │
│                          │  (SQLite)    │                    │
│                          └──────┬───────┘                    │
│                                 │                            │
│              ┌──────────────────┼──────────────────┐         │
│              │                  │                  │         │
│       ┌──────▼──────┐    ┌─────▼─────┐    ┌──────▼──────┐  │
│       │ AWS MQTT    │    │    FTP    │    │    Web      │  │
│       │ Publisher   │    │ Publisher │    │  Interface  │  │
│       └──────┬──────┘    └─────┬─────┘    └─────────────┘  │
│              │                  │                            │
└──────────────┼──────────────────┼────────────────────────────┘
               │                  │
               │ MQTT/TLS         │ FTP/SFTP
               │                  │
┌──────────────▼──────────────────▼────────────────────────────┐
│                         AWS CLOUD                             │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  IoT Core    │    │      S3      │    │  FTP Server  │  │
│  │   (MQTT)     │    │   (Images)   │    │  (Backup)    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘  │
│         │                   │                                │
│  ┌──────▼───────────────────▼───────┐                       │
│  │       IoT Rules Engine            │                       │
│  └──────┬────────────────────────────┘                       │
│         │                                                    │
│  ┌──────▼──────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Timestream │    │   Lambda     │    │  CloudWatch  │  │
│  │  (Metrics)  │    │ (Processing) │    │  (Alerts)    │  │
│  └─────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### MQTT Topic Structure

```
transformers/
├── {site_id}/
│   ├── telemetry              # Real-time temperature data (QoS 1)
│   ├── heartbeat              # Device health (QoS 0)
│   ├── images/metadata        # Image upload notifications (QoS 1)
│   ├── alerts                 # Temperature threshold alerts (QoS 1)
│   └── commands               # Remote control (QoS 1)
│       ├── config/update      # Configuration updates
│       ├── roi/update         # ROI configuration
│       └── system/restart     # System control
```

### Data Transmission Strategy

| Data Type | Frequency | Method | Size | Priority |
|-----------|-----------|--------|------|----------|
| Temperature readings | 1 min | MQTT | ~2 KB | High |
| ROI statistics | 1 min | MQTT | ~5 KB | High |
| Thermal frames (.npy) | 10 min | S3 | ~3 KB | Medium |
| Visual snapshots (.jpg) | 30 min | S3 | ~200 KB | Medium |
| Motion videos (.h264) | On event | S3 | ~10 MB | Low |
| Heartbeat | 5 min | MQTT | ~1 KB | High |
| System logs | 1 hour | FTP | ~100 KB | Low |

**Bandwidth Estimate**: ~15 MB/hour (normal operation)

---

## 3. Deployment Phases

### Phase 1: Development Integration (Week 1-2)

**Objective**: Connect all components and enable production mode

- [ ] Integrate AWS publisher into main.py
- [ ] Integrate FTP publisher into main.py
- [ ] Create thermal frame serialization/upload pipeline
- [ ] Create video upload pipeline
- [ ] Remove "TEST MODE" markers
- [ ] Add production configuration validation
- [ ] Implement health check endpoints

**Deliverable**: Fully integrated system running in staging environment

### Phase 2: Testing & Validation (Week 3)

**Objective**: Ensure reliability and correctness

- [ ] Unit tests for data publishers
- [ ] Integration tests for complete data pipeline
- [ ] Network failure simulation tests
- [ ] Load testing (24-hour continuous operation)
- [ ] Certificate rotation testing
- [ ] AWS IoT integration verification
- [ ] FTP integration verification

**Deliverable**: Validated system with >99% uptime in test environment

### Phase 3: Site Provisioning Automation (Week 4)

**Objective**: Create deployment tools

- [ ] Site provisioning script
- [ ] AWS IoT thing creation automation
- [ ] Certificate generation and installation
- [ ] Configuration template generator
- [ ] Deployment validation script
- [ ] Rollback procedures

**Deliverable**: One-command site deployment capability

### Phase 4: Pilot Deployment (Week 5-6)

**Objective**: Deploy to 1-2 pilot sites

- [ ] Select pilot sites
- [ ] Provision AWS resources
- [ ] Deploy to Raspberry Pi devices
- [ ] Monitor for 2 weeks
- [ ] Collect feedback
- [ ] Fix issues

**Deliverable**: Proven deployment in real-world environment

### Phase 5: Full Rollout (Week 7+)

**Objective**: Deploy to all sites

- [ ] Deploy to remaining sites
- [ ] Create operations runbook
- [ ] Train support staff
- [ ] Set up monitoring dashboards
- [ ] Establish maintenance schedule

**Deliverable**: Production system across all sites

---

## 4. Implementation Tasks

### 4.1 Enable Production Mode

**File**: `src/main.py`

**Changes**:
```python
# Remove "TEST MODE" from logging
# Enable AWS publisher when configured
# Enable FTP publisher when configured
# Add data upload pipeline
```

**Steps**:
1. Add `production_mode` config flag
2. Conditional initialization of publishers
3. Connect thermal data to AWS MQTT
4. Connect images/videos to S3/FTP
5. Add error handling and fallback to local storage

### 4.2 Thermal Data Upload Pipeline

**New File**: `src/data_uploader.py`

**Purpose**: Orchestrate data uploads to AWS and FTP

**Features**:
- Temperature data → MQTT every minute
- Thermal frames → S3 every 10 minutes
- Snapshots → S3 after capture
- Videos → S3 after recording
- Logs → FTP daily

### 4.3 Configuration Management

**Updates**:
- `config/site_config.template.yaml` - Add production flags
- `config/aws_config.template.yaml` - Finalize topic structure
- Add environment detection (dev/staging/prod)

### 4.4 Site Provisioning Script

**New File**: `scripts/provision_site.sh`

**Function**:
```bash
#!/bin/bash
# Usage: ./provision_site.sh <SITE_ID> <SITE_NAME>

# 1. Create AWS IoT Thing
# 2. Generate certificates
# 3. Attach policy
# 4. Create S3 bucket prefix
# 5. Generate site configuration
# 6. Package for deployment
```

### 4.5 Health Check API

**Add to**: `src/camera_web_interface.py`

**New Endpoints**:
```python
@app.route('/health/deep')
def deep_health_check():
    return {
        'thermal_camera': check_thermal_camera(),
        'visual_camera': check_visual_camera(),
        'aws_connection': check_aws_connection(),
        'ftp_connection': check_ftp_connection(),
        'disk_space': check_disk_space(),
        'network': check_network(),
        'status': 'healthy' | 'degraded' | 'unhealthy'
    }
```

### 4.6 CloudWatch Metrics

**New File**: `src/cloudwatch_publisher.py`

**Metrics to Track**:
- Composite temperature
- Max ROI temperature
- Camera uptime
- Data upload success rate
- Network connectivity %
- Disk usage
- CPU/Memory usage

### 4.7 Alert System

**Integration**: AWS IoT Rules → SNS → Email/SMS

**Alert Conditions**:
- Temperature > Emergency threshold
- Device offline > 10 minutes
- Disk space < 10%
- Upload failures > 10 consecutive
- Network down > 5 minutes

---

## 5. Testing Strategy

### 5.1 Unit Tests

**Coverage**:
- [ ] AWSPublisher connection/reconnection
- [ ] FTPPublisher upload/retry
- [ ] DataProcessor ROI calculations
- [ ] ThermalCapture frame acquisition
- [ ] Local buffer storage/retrieval

**Framework**: pytest

### 5.2 Integration Tests

**Scenarios**:
- [ ] End-to-end data flow (camera → AWS)
- [ ] Network failure → local buffering → retry
- [ ] Configuration updates via MQTT
- [ ] ROI changes reflected in telemetry
- [ ] Motion detection → video upload

**Environment**: Docker Compose with LocalStack for AWS simulation

### 5.3 Performance Tests

**Metrics**:
- [ ] CPU usage under load < 50%
- [ ] Memory usage < 500 MB
- [ ] Thermal capture latency < 1s
- [ ] MQTT publish latency < 500ms
- [ ] 24-hour stability test

### 5.4 Security Tests

**Checks**:
- [ ] Certificate validation
- [ ] TLS connection enforcement
- [ ] No hardcoded credentials
- [ ] Proper file permissions
- [ ] Web interface authentication

---

## 6. Deployment Procedures

### 6.1 New Site Deployment

**Prerequisites**:
- Raspberry Pi 4 (4GB+ RAM)
- MLX90640 thermal camera
- Pi Camera 3
- Internet connection (Ethernet preferred)
- AWS account with IoT Core enabled
- FTP server (optional)

**Steps**:

```bash
# 1. Provision site in AWS
./scripts/provision_site.sh SITE_001 "Downtown Substation"

# 2. Download deployment package
scp site_SITE_001_deployment.tar.gz pi@192.168.1.100:/home/pi/

# 3. SSH to Raspberry Pi
ssh pi@192.168.1.100

# 4. Extract and run installer
tar -xzf site_SITE_001_deployment.tar.gz
cd transformer-monitor
sudo ./scripts/install.sh

# 5. Verify installation
./scripts/verify_deployment.sh

# 6. Start service
sudo systemctl start transformer-monitor
sudo systemctl enable transformer-monitor

# 7. Check status
sudo systemctl status transformer-monitor
curl http://localhost:5000/health/deep
```

### 6.2 Configuration Update

**Remote Update via MQTT**:
```bash
# Publish config update command
aws iot-data publish \
    --topic "transformers/SITE_001/commands/config/update" \
    --payload file://new_config.json \
    --qos 1
```

**Manual Update**:
```bash
# SSH to site
ssh pi@<SITE_IP>

# Edit configuration
sudo nano /data/config/site_config.yaml

# Restart service
sudo systemctl restart transformer-monitor
```

### 6.3 Software Update

**Rolling Update**:
```bash
# 1. Pull new version
cd /home/pi/transformer-monitor
git pull origin main

# 2. Rebuild Docker image
docker build -t transformer-monitor:latest .

# 3. Restart service
sudo systemctl restart transformer-monitor

# 4. Monitor logs
sudo journalctl -u transformer-monitor -f
```

### 6.4 Rollback Procedure

```bash
# 1. Stop service
sudo systemctl stop transformer-monitor

# 2. Revert to previous version
git checkout <previous_commit_hash>

# 3. Rebuild
docker build -t transformer-monitor:latest .

# 4. Restart
sudo systemctl start transformer-monitor
```

---

## 7. Monitoring & Maintenance

### 7.1 Real-Time Monitoring

**CloudWatch Dashboard**:
- Site temperature map
- Alert timeline
- Upload success rates
- Device connectivity status
- Network health

**Access**: https://console.aws.amazon.com/cloudwatch/

### 7.2 Log Aggregation

**Options**:
1. **CloudWatch Logs**: Real-time streaming
2. **FTP Daily**: Long-term archive
3. **Local**: Last 7 days on device

**Log Levels**:
- ERROR: Critical issues requiring immediate attention
- WARNING: Degraded performance, automatic recovery
- INFO: Normal operations
- DEBUG: Detailed troubleshooting (disabled in production)

### 7.3 Maintenance Schedule

**Daily**:
- [ ] Check CloudWatch dashboard
- [ ] Review alerts
- [ ] Verify all sites online

**Weekly**:
- [ ] Review temperature trends
- [ ] Check disk usage
- [ ] Validate backups

**Monthly**:
- [ ] Software updates
- [ ] Certificate expiry check
- [ ] Performance review
- [ ] Capacity planning

**Quarterly**:
- [ ] On-site inspection
- [ ] Camera calibration
- [ ] Hardware health check
- [ ] ROI configuration review

### 7.4 Backup Strategy

**What to Backup**:
- Configuration files
- ROI definitions
- Certificates
- Historical thermal data (30 days)
- Video archive (7 days)

**Backup Locations**:
1. S3 (primary)
2. FTP server (secondary)
3. Local device (temporary)

**Retention**:
- Thermal data: 1 year
- Videos: 30 days
- Snapshots: 90 days
- Logs: 90 days

---

## 8. Security Considerations

### 8.1 Certificate Management

**AWS IoT Certificates**:
- Unique certificate per device
- Stored in `/data/certs/` (restrictive permissions)
- Policy: Device can only publish to own topics
- Rotation: Annually or on compromise

**Generation**:
```bash
# Automated via provision_site.sh
aws iot create-keys-and-certificate \
    --set-as-active \
    --certificate-pem-outfile certificate.pem.crt \
    --public-key-outfile public.pem.key \
    --private-key-outfile private.pem.key
```

### 8.2 Network Security

**Firewall Rules** (Raspberry Pi):
```bash
# Allow outbound HTTPS, MQTT, FTP
# Allow inbound port 5000 (web interface) from local network only
# Deny all other inbound
```

**Recommended**:
- VPN for remote access
- VPC with private subnets for AWS resources
- Security groups restricting IoT Core access

### 8.3 Web Interface Security

**Production Settings**:
```yaml
pi_camera:
  live_view:
    require_auth: true
    username: <unique_per_site>
    password: <strong_password>
    https: true  # Use reverse proxy with Let's Encrypt
    allowed_ips:  # Whitelist
      - 192.168.1.0/24
```

### 8.4 Data Encryption

- **In Transit**: TLS 1.2+ for all connections
- **At Rest**: S3 server-side encryption (AES-256)
- **Local**: Encrypted SQLite database (optional)

### 8.5 Access Control

**AWS IAM Policy** (site device):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect",
        "iot:Publish"
      ],
      "Resource": [
        "arn:aws:iot:region:account:client/${iot:Connection.Thing.ThingName}",
        "arn:aws:iot:region:account:topic/transformers/${iot:Connection.Thing.ThingName}/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["iot:Subscribe", "iot:Receive"],
      "Resource": [
        "arn:aws:iot:region:account:topicfilter/transformers/${iot:Connection.Thing.ThingName}/commands/*",
        "arn:aws:iot:region:account:topic/transformers/${iot:Connection.Thing.ThingName}/commands/*"
      ]
    }
  ]
}
```

---

## 9. Cost Estimation

### Per-Site Monthly Cost (AWS)

| Service | Usage | Cost |
|---------|-------|------|
| IoT Core | ~43k messages/month (1/min) | $0.22 |
| IoT Core | ~2k connections/month | $0.02 |
| S3 Storage | ~5 GB thermal + 20 GB video | $0.58 |
| S3 PUT | ~1500 uploads/month | $0.01 |
| Data Transfer | ~10 GB/month | $0.90 |
| CloudWatch | Custom metrics + logs | $0.30 |
| **Total** | | **~$2.00/site/month** |

**For 100 sites**: ~$200/month

### One-Time Costs

- Raspberry Pi 4 (4GB): $55
- MLX90640 sensor: $60
- Pi Camera 3: $25
- Case + power supply: $20
- MicroSD card (64GB): $15
- **Total per site**: $175

---

## 10. Success Criteria

**Technical**:
- [ ] 99.5% uptime per site
- [ ] <1% data loss
- [ ] <5 minute alert latency
- [ ] <60 second recovery from network failure
- [ ] All sites reporting within 10 minutes of deployment

**Operational**:
- [ ] <4 hour mean time to resolution
- [ ] <15 minute deployment per new site
- [ ] Zero manual intervention for normal operations
- [ ] Complete audit trail for all temperature events

**Business**:
- [ ] Operational cost <$3/site/month
- [ ] ROI positive within 12 months
- [ ] Scalable to 500+ sites

---

## 11. Risk Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Network outage | High | Medium | Local buffering, retry logic, cellular backup |
| Hardware failure | High | Low | Spare units, rapid replacement SLA |
| Certificate expiry | Medium | Low | Automated monitoring, 30-day warning |
| AWS service outage | Medium | Very Low | FTP fallback, local storage |
| Data breach | High | Very Low | Encryption, least-privilege access |
| Power failure | Medium | Medium | UPS backup, graceful shutdown |

---

## 12. Next Steps

### Immediate (This Week)
1. Review and approve this deployment plan
2. Set up AWS account and IoT Core
3. Create development environment
4. Start Phase 1 implementation

### Short-Term (Weeks 2-4)
1. Complete integration work
2. Execute testing plan
3. Develop provisioning scripts
4. Select pilot sites

### Long-Term (Weeks 5+)
1. Pilot deployment
2. Iterate based on feedback
3. Full rollout
4. Continuous improvement

---

## Appendix

### A. Required AWS Services
- AWS IoT Core
- Amazon S3
- AWS IoT Rules
- Amazon CloudWatch
- Amazon SNS (for alerts)
- AWS Lambda (optional, for data processing)
- Amazon Timestream (optional, for time-series data)

### B. Environment Variables

```bash
# Site Configuration
SITE_ID=SITE_001
SITE_NAME="Downtown Substation"
SITE_ADDRESS="123 Main St, City"
TRANSFORMER_SN=TX-12345

# AWS IoT
IOT_ENDPOINT=xxxxxx.iot.us-east-1.amazonaws.com
IOT_THING_NAME=transformer-monitor-SITE_001
AWS_REGION=us-east-1

# AWS S3
S3_BUCKET_NAME=transformer-monitor-data

# FTP (Optional)
FTP_HOST=ftp.example.com
FTP_USERNAME=transformer_monitor
FTP_PASSWORD=<secure_password>

# System
LOG_LEVEL=INFO
CAPTURE_INTERVAL=60
HEARTBEAT_INTERVAL=300
```

### C. Useful Commands

```bash
# Check service status
systemctl status transformer-monitor

# View logs
journalctl -u transformer-monitor -f

# Test AWS connection
aws iot-data publish --topic test/connection --payload '{"test": true}'

# Check disk space
df -h /data

# Monitor network
watch -n 1 'cat /proc/net/dev'

# Restart service
sudo systemctl restart transformer-monitor

# Update configuration
sudo nano /data/config/site_config.yaml
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Author**: Claude (AI Assistant)
**Status**: Draft - Awaiting Approval
