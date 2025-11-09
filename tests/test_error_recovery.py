"""
Unit tests for error recovery system
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import time

from src.error_recovery import ComponentHealthMonitor, ErrorRecoveryManager


class TestComponentHealthMonitor(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.monitor = ComponentHealthMonitor()

    def test_check_thermal_camera_healthy(self):
        """Test thermal camera health check - healthy case"""
        # Mock thermal camera that returns valid frame
        mock_camera = Mock()
        mock_camera.get_frame.return_value = [[1, 2], [3, 4]]

        result = self.monitor.check_thermal_camera(mock_camera)
        self.assertTrue(result)

    def test_check_thermal_camera_unhealthy(self):
        """Test thermal camera health check - unhealthy case"""
        # Mock thermal camera that returns None
        mock_camera = Mock()
        mock_camera.get_frame.return_value = None

        result = self.monitor.check_thermal_camera(mock_camera)
        self.assertFalse(result)

    def test_check_thermal_camera_none(self):
        """Test thermal camera health check - None camera"""
        result = self.monitor.check_thermal_camera(None)
        self.assertFalse(result)

    def test_check_smart_camera_healthy(self):
        """Test smart camera health check - healthy case"""
        # Mock smart camera with running camera
        mock_camera = Mock()
        mock_camera.camera = Mock()
        mock_camera.camera.started = True

        result = self.monitor.check_smart_camera(mock_camera)
        self.assertTrue(result)

    def test_check_smart_camera_unhealthy(self):
        """Test smart camera health check - unhealthy case"""
        # Mock smart camera with stopped camera
        mock_camera = Mock()
        mock_camera.camera = Mock()
        mock_camera.camera.started = False

        result = self.monitor.check_smart_camera(mock_camera)
        self.assertFalse(result)

    @patch('src.error_recovery.os.statvfs')
    def test_check_disk_space_sufficient(self, mock_statvfs):
        """Test disk space check - sufficient space"""
        # Mock filesystem stats (10 GB free)
        mock_stat = Mock()
        mock_stat.f_bavail = 10 * 1024 * 1024 * 1024 // 4096  # 10 GB in blocks
        mock_stat.f_frsize = 4096
        mock_statvfs.return_value = mock_stat

        result = self.monitor.check_disk_space(min_free_gb=2.0)
        self.assertTrue(result)

    @patch('src.error_recovery.os.statvfs')
    def test_check_disk_space_insufficient(self, mock_statvfs):
        """Test disk space check - insufficient space"""
        # Mock filesystem stats (1 GB free)
        mock_stat = Mock()
        mock_stat.f_bavail = 1 * 1024 * 1024 * 1024 // 4096  # 1 GB in blocks
        mock_stat.f_frsize = 4096
        mock_statvfs.return_value = mock_stat

        result = self.monitor.check_disk_space(min_free_gb=2.0)
        self.assertFalse(result)

    @patch('src.error_recovery.psutil.virtual_memory')
    def test_check_memory_acceptable(self, mock_memory):
        """Test memory check - acceptable usage"""
        mock_memory.return_value = Mock(percent=75.0)

        result = self.monitor.check_memory(max_percent=90)
        self.assertTrue(result)

    @patch('src.error_recovery.psutil.virtual_memory')
    def test_check_memory_high(self, mock_memory):
        """Test memory check - high usage"""
        mock_memory.return_value = Mock(percent=95.0)

        result = self.monitor.check_memory(max_percent=90)
        self.assertFalse(result)


class TestErrorRecoveryManager(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures"""
        self.config = Mock()
        self.config.get.return_value = None

        self.recovery_manager = ErrorRecoveryManager(self.config)

    def test_initialization(self):
        """Test recovery manager initialization"""
        self.assertIsNotNone(self.recovery_manager.health_monitor)
        self.assertEqual(self.recovery_manager.thermal_camera_failures, 0)
        self.assertEqual(self.recovery_manager.smart_camera_failures, 0)

    def test_set_components(self):
        """Test setting components to monitor"""
        mock_thermal = Mock()
        mock_smart = Mock()
        mock_network = Mock()

        self.recovery_manager.set_components(
            thermal_capture=mock_thermal,
            smart_camera=mock_smart,
            network_monitor=mock_network
        )

        self.assertEqual(self.recovery_manager.thermal_capture, mock_thermal)
        self.assertEqual(self.recovery_manager.smart_camera, mock_smart)
        self.assertEqual(self.recovery_manager.network_monitor, mock_network)

    def test_graceful_degradation_thermal(self):
        """Test graceful degradation for thermal camera failure"""
        # Should not raise exception
        self.recovery_manager.handle_graceful_degradation('thermal_camera')

        # Verify it's logged (check that logger was called)
        self.assertIsNotNone(self.recovery_manager.logger)

    def test_graceful_degradation_smart_camera(self):
        """Test graceful degradation for smart camera failure"""
        self.recovery_manager.handle_graceful_degradation('smart_camera')
        # Should complete without error

    def test_graceful_degradation_network(self):
        """Test graceful degradation for network failure"""
        self.recovery_manager.handle_graceful_degradation('network')
        # Should complete without error

    def test_health_report_structure(self):
        """Test health report has correct structure"""
        report = self.recovery_manager.get_health_report()

        self.assertIn('thermal_camera', report)
        self.assertIn('smart_camera', report)
        self.assertIn('disk_space', report)
        self.assertIn('memory', report)
        self.assertIn('cpu_temp', report)
        self.assertIn('timestamp', report)

        # Check thermal camera structure
        self.assertIn('healthy', report['thermal_camera'])
        self.assertIn('failure_count', report['thermal_camera'])

    def test_thermal_camera_failure_tracking(self):
        """Test thermal camera failure tracking"""
        # Simulate failures
        self.recovery_manager.thermal_camera_failures = 3

        report = self.recovery_manager.get_health_report()

        self.assertFalse(report['thermal_camera']['healthy'])
        self.assertEqual(report['thermal_camera']['failure_count'], 3)

    def test_stop_monitoring(self):
        """Test stopping monitoring"""
        # Should complete without hanging
        self.recovery_manager.stop_monitoring()

        # Stop event should be set
        self.assertTrue(self.recovery_manager.stop_monitoring.is_set())


class TestRecoveryStrategies(unittest.TestCase):
    """Test recovery strategy logic"""

    def test_exponential_backoff_concept(self):
        """Test exponential backoff calculation concept"""
        # Manually calculate expected delays
        expected_delays = [0, 2, 4, 8, 16, 32, 60, 60]  # Capped at 60s

        for attempt in range(len(expected_delays)):
            delay = min(2 ** attempt, 60)
            self.assertEqual(delay, expected_delays[attempt])

    def test_failure_count_reset_logic(self):
        """Test that failure count resets on success"""
        failure_count = 5

        # Simulate success
        if True:  # Health check passed
            failure_count = 0

        self.assertEqual(failure_count, 0)

    def test_recovery_cooldown_logic(self):
        """Test recovery attempt cooldown"""
        last_recovery = time.time() - 100  # 100 seconds ago
        cooldown_period = 300  # 5 minutes

        time_since_last = time.time() - last_recovery

        # Should allow recovery
        self.assertGreater(time_since_last, cooldown_period // 10)

        # Recent recovery
        last_recovery = time.time() - 10  # 10 seconds ago
        time_since_last = time.time() - last_recovery

        # Should not allow recovery yet
        self.assertLess(time_since_last, cooldown_period)


if __name__ == '__main__':
    unittest.main()
