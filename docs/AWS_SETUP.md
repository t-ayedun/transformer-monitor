# AWS IoT Core Setup Guide

This guide details how to configure AWS IoT Core and related services for the Transformer Monitor system.

## Prerequisites

- AWS Account with Administrator access
- AWS CLI installed and configured
- Domain/Region where you want to deploy (e.g., `us-east-1`)

## 1. Create IoT Thing

1. **Log in to AWS Console** and navigate to **IoT Core**.
2. Go to **Manage** > **All devices** > **Things**.
3. Click **Create things**.
4. Select **Create single thing**.
5. **Thing name**: Enter a unique name for your device (e.g., `transformer-monitor-SITE_001`).
    - *Note: This MUST match the `IOT_THING_NAME` variable on your device.*
6. **Device Shadow**: Select "No shadow" (we use MQTT topics directly).
7. **Device Certificate**: Select "Auto-generate a new certificate (recommended)".
8. Click **Next** until you reach the download page.

## 2. Certificates

> [!IMPORTANT]
> You only get ONE chance to download these files.

1. Download:
    - **Device Certificate** (`xxxxxxxx-certificate.pem.crt`) → Rename to `certificate.pem.crt`
    - **Private Key** (`xxxxxxxx-private.pem.key`) → Rename to `private.pem.key`
    - **Amazon Root CA 1** → Rename to `AmazonRootCA1.pem`
2. **Setup on Device**:
    - These specific filenames are expected by the code.
    - Upload them to `/data/certs/` on your Raspberry Pi.

## 3. Create IoT Policy

The device needs permission to connect, publish, and subscribe.

1. Go to **Security** > **Policies**.
2. Click **Create policy**.
3. **Name**: `TransformerMonitorPolicy`
4. **Policy document**: Use the JSON below (replace `<account-id>` and `<region>`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "arn:aws:iot:<region>:<account-id>:client/${iot:Connection.Thing.ThingName}"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": [
        "arn:aws:iot:<region>:<account-id>:topic/dt/transformer/${iot:Connection.Thing.ThingName}/telemetry",
        "arn:aws:iot:<region>:<account-id>:topic/dt/transformer/${iot:Connection.Thing.ThingName}/heartbeat"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": "arn:aws:iot:<region>:<account-id>:topicfilter/cmd/transformer/${iot:Connection.Thing.ThingName}/+"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Receive",
      "Resource": "arn:aws:iot:<region>:<account-id>:topic/cmd/transformer/${iot:Connection.Thing.ThingName}/+"
    }
  ]
}
```

5. **Attach Policy**:
    - Go to **Security** > **Certificates**.
    - Click on the certificate you just created.
    - Click **Policies** tab > **Attach policies**.
    - Select `TransformerMonitorPolicy`.

## 4. S3 Bucket Setup (Images)

1. Navigate to **S3**.
2. Click **Create bucket**.
3. **Bucket name**: e.g., `transformer-thermal-images-prod` (Must be globally unique).
4. **Region**: Same as IoT Core (recommended).
5. **Block Public Access**: **Block all public access** (Checked).
6. Click **Create bucket**.

### IoT Role for S3 Access (Optional - if using Greengrass or direct AssumeRole)

*Note: The current `aws_publisher.py` uses standard boto3. To allow the device to upload directly to S3, you typically attach an IAM Role alias or use Access Keys. For IoT devices in production, we recommend using **IoT Credential Provider** so the certificate is used to authenticate S3 requests.*

**Simplified Setup (IAM User with Access Keys):**
*For testing/prototyping only.*
1. Create IAM User `transformer-device-user`.
2. Attach policy `AmazonS3FullAccess` (or restricted to specific bucket).
3. Generate Access Keys.
4. Pass as env vars (NOT RECOMMENDED for production).

**Recommended Setup (IoT Credential Provider):**
1. Create IAM Role `TransformerMonitorRole` with S3 Write permissions.
2. Create Role Alias in IoT Core.
3. Update IoT Policy to allow `iot:AssumeRoleWithCertificate`.

## 5. Get IoT Endpoint

1. Go to **Settings** in AWS IoT Core console.
2. Find **Device data endpoint**.
3. Copy the URL (e.g., `xxxxxxxxxxxxx-ats.iot.us-east-1.amazonaws.com`).
4. This is your `IOT_ENDPOINT` variable.

## 6. Verification

Run the Python test script (if available) or check logs on the device:

```bash
balena logs <device-uuid> | grep "Connected to AWS IoT Core"
```
