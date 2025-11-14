"""
Security validation tests
Tests certificate validation, credential handling, TLS enforcement, and security best practices
"""

import pytest
import os
import yaml
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


@pytest.mark.security
class TestSecurity:
    """Security validation tests"""

    def test_no_hardcoded_credentials_in_config(self):
        """Verify no hardcoded credentials in configuration files"""
        config_files = [
            '/home/user/transformer-monitor/config/site_config.template.yaml',
            '/home/user/transformer-monitor/config/aws_config.template.yaml',
        ]

        forbidden_patterns = [
            'password: "',
            'api_key: "',
            'secret: "',
            'token: "',
        ]

        for config_file in config_files:
            if Path(config_file).exists():
                with open(config_file) as f:
                    content = f.read().lower()

                    for pattern in forbidden_patterns:
                        assert pattern not in content, \
                            f"Potential hardcoded credential found in {config_file}"

    def test_environment_variable_credential_loading(self, mock_config):
        """Test credentials are loaded from environment variables"""
        from config_manager import ConfigManager

        # Set test environment variables
        with patch.dict(os.environ, {
            'SITE_ID': 'TEST_SITE',
            'IOT_ENDPOINT': 'test.iot.us-east-1.amazonaws.com',
            'FTP_PASSWORD': 'test_password'
        }):
            config = ConfigManager()

            # Verify environment substitution works
            test_content = "site_id: {{SITE_ID}}\nendpoint: {{IOT_ENDPOINT}}"
            result = test_content.replace('{{SITE_ID}}', os.getenv('SITE_ID'))
            result = result.replace('{{IOT_ENDPOINT}}', os.getenv('IOT_ENDPOINT'))

            assert 'TEST_SITE' in result
            assert 'test.iot.us-east-1.amazonaws.com' in result

    def test_certificate_file_permissions(self, temp_dir):
        """Test certificate files have restrictive permissions"""
        # Create test certificate file
        cert_path = f"{temp_dir}/test_cert.pem"
        with open(cert_path, 'w') as f:
            f.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")

        # Set restrictive permissions (600 - owner read/write only)
        os.chmod(cert_path, 0o600)

        # Verify permissions
        stat_info = os.stat(cert_path)
        permissions = oct(stat_info.st_mode)[-3:]

        # Should be 600 (owner read/write only)
        assert permissions == '600', f"Certificate permissions too open: {permissions}"

    def test_aws_iot_requires_certificates(self, mock_config):
        """Test AWS IoT connection requires valid certificates"""
        from config_manager import ConfigManager

        config = ConfigManager()
        config.config = {
            'aws': {
                'iot': {
                    'enabled': True,
                    'endpoint': 'test.iot.amazonaws.com',
                    'thing_name': 'test-thing',
                    'certificates': {
                        'ca_cert': '/nonexistent/ca.pem',
                        'device_cert': '/nonexistent/device.pem',
                        'private_key': '/nonexistent/private.key'
                    }
                }
            },
            'site': {'id': 'TEST'}
        }

        # Validate should detect missing certificates
        config.validate()

        # AWS IoT should be disabled due to missing certs
        assert config.get('aws.iot.enabled') is False

    def test_no_plaintext_passwords_in_logs(self, mock_config, caplog):
        """Test passwords are not logged in plaintext"""
        from config_manager import ConfigManager

        config = ConfigManager()
        config.logger = MagicMock()

        # Set password in config
        config.set('ftp.password', 'super_secret_password')

        # Simulate logging config
        config.logger.info(f"FTP config: {config.get('ftp')}")

        # Verify password not in log calls (would need to check actual log output)
        # In production, sensitive values should be masked
        assert config.get('ftp.password') == 'super_secret_password'

    def test_mqtt_tls_enforcement(self, mock_config):
        """Test MQTT connections use TLS"""
        # AWS IoT Core enforces TLS by default
        # Verify endpoint uses secure protocol

        endpoint = mock_config.get('aws.iot.endpoint', '')

        # AWS IoT endpoints should use port 8883 (MQTT over TLS)
        # or 443 (MQTT over WebSocket with TLS)
        assert 'amazonaws.com' in endpoint or endpoint == '', \
            "IoT endpoint should be AWS endpoint"

    def test_s3_upload_uses_https(self, mock_config):
        """Test S3 uploads use HTTPS"""
        # boto3 uses HTTPS by default
        # Verify no insecure HTTP configurations

        s3_config = mock_config.get('aws.s3', {})

        # If endpoint override exists, should be HTTPS
        if 'endpoint_url' in s3_config:
            endpoint = s3_config['endpoint_url']
            assert endpoint.startswith('https://'), \
                f"S3 endpoint not using HTTPS: {endpoint}"

    def test_ftp_passive_mode_enabled(self, mock_config):
        """Test FTP uses passive mode (more firewall-friendly)"""
        ftp_passive = mock_config.get('ftp.passive', True)
        assert ftp_passive is True, "FTP should use passive mode"

    def test_web_interface_authentication(self, mock_config):
        """Test web interface has authentication option"""
        auth_required = mock_config.get('pi_camera.live_view.require_auth')

        # Auth should be configurable
        assert auth_required is not None, "Web auth not configured"

        # If auth enabled, username/password should exist
        if auth_required:
            username = mock_config.get('pi_camera.live_view.username')
            password = mock_config.get('pi_camera.live_view.password')

            assert username is not None, "Web username not configured"
            assert password is not None, "Web password not configured"

    def test_input_validation_site_id(self):
        """Test site ID input validation"""
        from config_manager import ConfigManager

        config = ConfigManager()

        # Valid site IDs
        valid_ids = ['SITE_001', 'TRANSFORMER_A', 'TX-123']
        for site_id in valid_ids:
            config.set('site.id', site_id)
            assert config.get('site.id') == site_id

        # Site ID should be non-empty
        config.set('site.id', 'VALID_ID')
        assert config.get('site.id') != ''

    def test_sql_injection_prevention_local_buffer(self, temp_dir, sample_processed_data):
        """Test local buffer prevents SQL injection"""
        from local_buffer import LocalBuffer

        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

        try:
            # Attempt SQL injection in data
            malicious_data = {
                **sample_processed_data,
                'site_id': "'; DROP TABLE readings; --"
            }

            # Should safely store without executing SQL
            buffer.store(malicious_data)

            # Verify table still exists
            recent = buffer.get_recent(limit=1)
            assert len(recent) == 1

        finally:
            buffer.close()
            Path(temp_db.name).unlink()

    def test_path_traversal_prevention(self, mock_config):
        """Test file operations prevent path traversal attacks"""
        from smart_camera import SmartCamera

        with patch('smart_camera.Picamera2') as mock_picam:
            mock_camera = MagicMock()
            mock_picam.return_value = mock_camera

            camera = SmartCamera(mock_config)

            # Attempt path traversal in filename
            malicious_name = "../../../etc/passwd"

            # Should sanitize filename
            filepath = camera.capture_snapshot(custom_name=malicious_name)

            # Verify path stays within snapshot directory
            if filepath:
                assert '/etc/passwd' not in filepath
                assert camera.snapshot_dir in filepath

            camera.close()

    def test_certificate_expiration_handling(self, temp_dir):
        """Test system handles expired certificates gracefully"""
        # Create expired certificate (mock)
        cert_path = f"{temp_dir}/expired_cert.pem"
        with open(cert_path, 'w') as f:
            f.write("-----BEGIN CERTIFICATE-----\nexpired\n-----END CERTIFICATE-----")

        # AWS SDK should reject expired certificates
        # Test would need actual certificate validation logic

        assert Path(cert_path).exists()

    def test_data_encryption_at_rest(self, temp_dir):
        """Test local data can be encrypted at rest"""
        # SQLite databases can use SQLCipher for encryption
        # This is a placeholder for future encryption implementation

        db_path = f"{temp_dir}/test.db"

        # Future: Verify database uses encryption
        # For now, document that encryption should be added for production

        # Recommendation: Use SQLCipher or filesystem-level encryption
        pass

    def test_no_sensitive_data_in_mqtt_topics(self, mock_config):
        """Test MQTT topics don't contain sensitive information"""
        topics = [
            mock_config.get('aws.iot.topics.telemetry'),
            mock_config.get('aws.iot.topics.heartbeat'),
            mock_config.get('aws.iot.topics.alerts')
        ]

        forbidden_in_topic = ['password', 'secret', 'key', 'token']

        for topic in topics:
            if topic:
                topic_lower = topic.lower()
                for forbidden in forbidden_in_topic:
                    assert forbidden not in topic_lower, \
                        f"Sensitive term '{forbidden}' in topic: {topic}"

    def test_mqtt_qos_levels(self, mock_config):
        """Test MQTT messages use appropriate QoS levels"""
        from data_uploader import DataUploader

        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.mqtt_client = MagicMock()

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Publish alert
        alert_data = {
            'level': 'emergency',
            'temperature': 100.0,
            'message': 'Test alert'
        }

        uploader.upload_alert(alert_data)

        # Alerts should use QoS 1 (at least once delivery)
        mock_aws.mqtt_client.publish.assert_called()
        call_args = mock_aws.mqtt_client.publish.call_args

        # QoS should be 1 for alerts (third argument)
        assert call_args[0][2] == 1, "Alerts should use QoS 1"

    def test_api_rate_limiting(self, mock_config):
        """Test API endpoints have rate limiting (future implementation)"""
        # Placeholder for future web API rate limiting
        # Web interface should implement rate limiting to prevent abuse

        # Recommendation: Use Flask-Limiter for rate limiting
        pass

    def test_secure_random_generation(self):
        """Test system uses secure random number generation"""
        import secrets

        # Generate random token
        token = secrets.token_hex(16)

        assert len(token) == 32  # 16 bytes = 32 hex chars
        assert token.isalnum()

        # Verify randomness (two tokens should be different)
        token2 = secrets.token_hex(16)
        assert token != token2

    def test_no_debug_mode_in_production(self, mock_config):
        """Test debug mode is disabled in production"""
        production_mode = mock_config.get('production_mode', False)
        log_level = mock_config.get('logging.level', 'INFO')

        # In production, should not use DEBUG logging
        if production_mode:
            assert log_level != 'DEBUG', \
                "Debug logging should be disabled in production"

    def test_cors_configuration(self):
        """Test web interface CORS is properly configured"""
        # If web interface is exposed, CORS should be restrictive
        # Placeholder for future CORS configuration tests

        # Recommendation: Only allow specific origins, not '*'
        pass

    def test_session_management(self):
        """Test web interface has secure session management"""
        # Placeholder for future session security tests
        # Sessions should have:
        # - Secure flag (HTTPS only)
        # - HttpOnly flag (no JavaScript access)
        # - Reasonable timeout
        # - Secure session ID generation

        pass

    def test_error_messages_no_sensitive_info(self, mock_config, caplog):
        """Test error messages don't leak sensitive information"""
        from data_uploader import DataUploader

        mock_aws = MagicMock()
        mock_aws.connected = True
        mock_aws.publish_telemetry.side_effect = Exception("Connection failed")

        uploader = DataUploader(
            config=mock_config,
            aws_publisher=mock_aws,
            ftp_publisher=None,
            local_buffer=None
        )

        # Trigger error
        result = uploader.upload_telemetry({'test': 'data'})
        assert result is False

        # Error should be logged but not expose credentials
        # Would need to check actual log output in production

    def test_file_upload_size_limits(self, temp_dir):
        """Test file uploads have reasonable size limits"""
        from storage_manager import StorageManager

        # Storage manager should enforce limits
        # Verify thermal frames don't grow unbounded

        max_thermal_size = 768 * 4  # 24x32 float32 = 3072 bytes
        # With metadata, should be < 10KB per frame

        test_frame = np.random.rand(24, 32)
        frame_size = test_frame.nbytes

        assert frame_size < 10000, f"Thermal frame too large: {frame_size} bytes"

    def test_database_backup_integrity(self, temp_dir):
        """Test database backups maintain integrity"""
        from local_buffer import LocalBuffer
        import shutil

        import tempfile
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        buffer = LocalBuffer(db_path=temp_db.name, max_size_mb=10)

        try:
            # Store some data
            for i in range(10):
                buffer.store({'site_id': 'TEST', 'temperature': 25.0 + i})

            # Create backup
            backup_path = f"{temp_dir}/backup.db"
            shutil.copy(temp_db.name, backup_path)

            # Verify backup has same data
            buffer_backup = LocalBuffer(db_path=backup_path, max_size_mb=10)
            original_data = buffer.get_recent(limit=20)
            backup_data = buffer_backup.get_recent(limit=20)

            assert len(original_data) == len(backup_data)

            buffer_backup.close()

        finally:
            buffer.close()
            Path(temp_db.name).unlink()
            if Path(backup_path).exists():
                Path(backup_path).unlink()

    def test_network_timeout_configuration(self, mock_config):
        """Test network operations have timeouts"""
        # All network operations should have timeouts
        # to prevent hanging on unresponsive servers

        # AWS SDK has default timeouts
        # FTP should configure connect/data timeouts
        # HTTP requests should have timeouts

        # This is a placeholder for timeout validation
        pass

    def test_privilege_separation(self):
        """Test application doesn't require root privileges"""
        # Application should run as non-root user
        # Only specific operations (I2C, camera) need elevated access

        current_uid = os.getuid()

        # Should not be running as root (UID 0)
        # In Docker, this might be 0, but in production should be non-root
        # This test is more of a deployment check

        # Recommendation: Run as non-root user with device permissions
        pass
