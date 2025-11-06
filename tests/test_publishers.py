"""
Unit tests for data publishers
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

from src.aws_publisher import AWSPublisher
from src.ftp_publisher import FTPPublisher


class TestAWSPublisher(unittest.TestCase):
    
    @patch('src.aws_publisher.AWSIoTMQTTClient')
    @patch('src.aws_publisher.boto3.client')
    def setUp(self, mock_boto, mock_mqtt):
        """Set up test fixtures"""
        self.mock_mqtt = mock_mqtt.return_value
        self.mock_s3 = mock_boto.return_value
        
        self.certs = {
            'ca_cert': '/tmp/ca.pem',
            'device_cert': '/tmp/cert.pem',
            'private_key': '/tmp/key.pem'
        }
        
        self.topics = {
            'telemetry': 'test/telemetry',
            'heartbeat': 'test/heartbeat'
        }
        
        # Create publisher
        with patch('src.aws_publisher.Path.exists', return_value=True):
            self.publisher = AWSPublisher(
                endpoint='test.iot.amazonaws.com',
                thing_name='test-thing',
                certs=self.certs,
                topics=self.topics
            )
    
    def test_initialization(self):
        """Test publisher initialization"""
        self.assertIsNotNone(self.publisher)
        self.assertEqual(self.publisher.endpoint, 'test.iot.amazonaws.com')
        self.assertEqual(self.publisher.thing_name, 'test-thing')
    
    def test_publish_telemetry(self):
        """Test publishing telemetry data"""
        self.publisher.connected = True
        
        test_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'site_id': 'TEST_001',
            'composite_temperature': 75.5
        }
        
        result = self.publisher.publish_telemetry(test_data)
        
        self.assertTrue(result)
        self.mock_mqtt.publish.assert_called_once()
        
        # Verify published data
        call_args = self.mock_mqtt.publish.call_args
        topic = call_args[0][0]
        payload = call_args[0][1]
        
        self.assertEqual(topic, 'test/telemetry')
        
        # Parse and verify JSON
        data = json.loads(payload)
        self.assertEqual(data['site_id'], 'TEST_001')
        self.assertEqual(data['composite_temperature'], 75.5)
    
    def test_publish_when_disconnected(self):
        """Test publishing when disconnected"""
        self.publisher.connected = False
        
        mock_buffer = Mock()
        self.publisher.local_buffer = mock_buffer
        
        test_data = {'test': 'data'}
        result = self.publisher.publish_telemetry(test_data)
        
        self.assertFalse(result)
        mock_buffer.store.assert_called_once_with(test_data)


class TestFTPPublisher(unittest.TestCase):
    
    @patch('src.ftp_publisher.ftplib.FTP')
    def setUp(self, mock_ftp_class):
        """Set up test fixtures"""
        self.mock_ftp = mock_ftp_class.return_value
        
        self.publisher = FTPPublisher(
            host='ftp.example.com',
            username='test_user',
            password='test_pass',
            remote_dir='/test_dir'
        )
    
    def test_initialization(self):
        """Test FTP publisher initialization"""
        self.assertIsNotNone(self.publisher)
        self.assertEqual(self.publisher.host, 'ftp.example.com')
        self.assertEqual(self.publisher.username, 'test_user')
    
    def test_upload_data(self):
        """Test uploading JSON data"""
        self.publisher.ftp = self.mock_ftp
        self.publisher.last_connection_time = 1000000000
        
        test_data = {
            'site_id': 'TEST_001',
            'temperature': 75.5
        }
        
        result = self.publisher.upload_data(test_data, 'test.json')
        
        self.assertTrue(result)
        self.mock_ftp.storbinary.assert_called_once()
        
        # Verify stats updated
        self.assertEqual(self.publisher.stats['uploads_success'], 1)
        self.assertGreater(self.publisher.stats['bytes_uploaded'], 0)
    
    def test_upload_batch(self):
        """Test batch upload"""
        self.publisher.ftp = self.mock_ftp
        self.publisher.last_connection_time = 1000000000
        
        test_data = [
            {'timestamp': '2025-01-01T00:00:00Z', 'temp': 75.0},
            {'timestamp': '2025-01-01T00:01:00Z', 'temp': 76.0},
            {'timestamp': '2025-01-01T00:02:00Z', 'temp': 77.0}
        ]
        
        result = self.publisher.upload_batch(test_data)
        
        self.assertTrue(result)
        
    def test_get_stats(self):
        """Test getting upload statistics"""
        self.publisher.stats['uploads_success'] = 10
        self.publisher.stats['uploads_failed'] = 2
        
        stats = self.publisher.get_stats()
        
        self.assertEqual(stats['uploads_success'], 10)
        self.assertEqual(stats['uploads_failed'], 2)
        self.assertAlmostEqual(stats['success_rate'], 10/12)


if __name__ == '__main__':
    unittest.main()