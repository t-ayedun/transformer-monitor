
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import numpy as np
import cv2
from flask import Flask

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from camera_web_interface import CameraWebInterface

class TestCameraWebInterface(unittest.TestCase):
    def setUp(self):
        self.mock_smart_camera = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.get.side_effect = lambda k, d=None: d
        self.mock_thermal_capture = MagicMock()
        self.mock_data_processor = MagicMock()
        self.mock_aws_publisher = MagicMock()

        # Mock camera capture
        self.mock_smart_camera.camera.capture_array.return_value = np.zeros((480, 640, 3), dtype=np.uint8)

        self.web_interface = CameraWebInterface(
            smart_camera=self.mock_smart_camera,
            config=self.mock_config,
            thermal_capture=self.mock_thermal_capture,
            data_processor=self.mock_data_processor,
            aws_publisher=self.mock_aws_publisher
        )
        self.web_interface.app.config['TESTING'] = True
        self.client = self.web_interface.app.test_client()

    def test_get_thermal_snapshot(self):
        # Set latest thermal frame
        frame = np.zeros((24, 32), dtype=np.float32)
        self.web_interface.update_thermal_frame(frame)

        response = self.client.get('/api/snapshot/thermal')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/jpeg')

    def test_get_visual_snapshot(self):
        response = self.client.get('/api/snapshot/visual')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/jpeg')
        self.mock_smart_camera.camera.capture_array.assert_called_with("main")

    def test_get_fusion_snapshot(self):
        # Set latest thermal frame
        frame = np.zeros((24, 32), dtype=np.float32)
        self.web_interface.update_thermal_frame(frame)

        response = self.client.get('/api/snapshot/fusion')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/jpeg')

    def test_invalid_snapshot_type(self):
        response = self.client.get('/api/snapshot/invalid')
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main()
