# FTP and cPanel Setup Guide

This guide explains how to set up an FTP account in cPanel for the Transformer Monitoring System and configure the system to upload data.

## 1. Create an FTP Account in cPanel

1. Log in to your cPanel account.
2. Navigate to the **Files** section and click on **FTP Accounts**.
3. Under **Add FTP Account**:
   - **Log In**: Enter a username (e.g., `transformer-monitor`).
   - **Domain**: Select the appropriate domain.
   - **Password**: Generate a strong password and save it securely.
   - **Directory**: Enter the path where you want data stored (e.g., `transformer-data`).
     - *Important*: Remove `public_html/` if you don't want the data to be publicly accessible via web browser. A path like `/home/username/transformer-data` is recommended.
   - **Quota**: Set to **Unlimited** or a sufficient limit (e.g., 10 GB).
4. Click **Create FTP Account**.

## 2. Recommended Folder Structure

The monitoring system will automatically create the following folder structure inside your FTP directory:

```
/transformer-data/
├── telemetry/
│   └── YYYY/
│       └── MM/
│           └── DD/
│               └── SITE_ID_telemetry_TIMESTAMP.json
├── thermal/
│   └── YYYY/
│       └── MM/
│           └── DD/
│               └── image_name.jpg
├── visual/
│   └── YYYY/
│       └── MM/
│           └── DD/
│               └── image_name.jpg
└── videos/
    └── YYYY/
        └── MM/
        └── DD/
            └── video_name.mp4
```

## 3. Configuration

Update your `site_config.yaml` file on the Raspberry Pi with the credentials:

```yaml
ftp:
  enabled: true
  host: "ftp.yourdomain.com"
  port: 21
  username: "transformer-monitor@yourdomain.com"
  password: "YOUR_STRONG_PASSWORD"
  remote_dir: "/transformer-data"  # Must match the directory set in cPanel (relative to FTP root)
  passive_mode: true
  
  # Intervals
  thermal_image_interval: 600  # Upload every 10 minutes
  telemetry_upload_interval: 300  # Upload every 5 minutes
  batch_telemetry: true
  organize_by_date: true
```

> **Security Tip**: Instead of storing the password in `site_config.yaml`, you can set the `FTP_PASSWORD` environment variable on the Raspberry Pi.

## 4. Troubleshooting

- **Connection Refused**: Check if your cPanel/Firewall blocks the Raspberry Pi's IP address.
- **Upload Failed**: Ensure the FTP user has "Write" permissions to the directory.
- **Passive Mode**: If transfers hang, ensure `passive_mode: true` is set (required for most cPanel servers behind NAT).
- **Path Issues**: Verify `remote_dir`. If you created an FTP account mapped specifically to `/transformer-data`, then `remote_dir` should irrelevant or `/` depending on server config. Usually, `/` is safe if the account is restricted to that folder.

## 5. Verification

To verify uploads:
1. Use an FTP client (like FileZilla) to log in with the created credentials.
2. Check if folders for the current date are created.
3. Download a JSON telemetry file and verify it contains valid timestamps and transformer metrics.
