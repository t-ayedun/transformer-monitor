# Transformer Monitor Test Suite

Comprehensive test suite for the Transformer Thermal Monitor system, covering unit tests, integration tests, performance tests, and security validation.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Continuous Integration](#continuous-integration)
- [Test Coverage](#test-coverage)
- [Troubleshooting](#troubleshooting)

## Overview

This test suite validates the complete transformer monitoring system, including:

- **Thermal capture and processing** - MLX90640 thermal camera integration
- **Data pipeline** - Local buffering, processing, and cloud upload
- **Network resilience** - Failure handling, retry logic, offline operation
- **Performance** - Latency, throughput, memory usage, stability
- **Security** - Credential handling, TLS enforcement, input validation

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── unit/                    # Unit tests for individual components
│   ├── test_data_processor.py
│   └── test_data_uploader.py
├── integration/             # Integration tests for complete flows
│   ├── test_data_pipeline.py
│   └── test_network_resilience.py
├── performance/             # Performance and load tests
│   └── test_load.py
├── security/                # Security validation tests
│   └── test_security.py
└── README.md               # This file
```

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock psutil
```

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Performance tests only
pytest -m performance

# Security tests only
pytest -m security

# Run fast tests only (exclude slow tests)
pytest -m "not slow"
```

### Run Specific Test Files

```bash
# Run data processor tests
pytest tests/unit/test_data_processor.py

# Run network resilience tests
pytest tests/integration/test_network_resilience.py -v

# Run specific test function
pytest tests/unit/test_data_processor.py::TestDataProcessor::test_threshold_emergency
```

### Run Tests Requiring Hardware

Tests that require actual hardware (thermal camera, Pi camera) are marked with `@pytest.mark.requires_hardware` and are skipped by default.

```bash
# Run hardware tests (only on Raspberry Pi with connected hardware)
pytest -m requires_hardware
```

## Test Categories

### Unit Tests

**Location:** `tests/unit/`

**Coverage:**
- `test_data_processor.py` - DataProcessor component (14 tests)
  - Frame processing and statistics
  - ROI processing and weighting
  - Composite temperature calculation
  - Threshold detection (warning, critical, emergency)
  - Emissivity correction

- `test_data_uploader.py` - DataUploader component (13 tests)
  - Telemetry upload via MQTT
  - Queued uploads (thermal frames, snapshots, videos)
  - Alert publishing
  - FTP log upload
  - Fallback to local buffer
  - Worker thread lifecycle

**Run:**
```bash
pytest -m unit -v
```

### Integration Tests

**Location:** `tests/integration/`

**Coverage:**
- `test_data_pipeline.py` - End-to-end data flows (10 tests)
  - Thermal capture → local buffer
  - Thermal capture → cloud upload
  - ROI alert pipeline
  - Snapshot capture and upload
  - Video recording and upload
  - Multiple captures in sequence

- `test_network_resilience.py` - Network failure scenarios (16 tests)
  - AWS disconnect/reconnect
  - MQTT publish timeouts
  - S3 upload retry logic
  - Queue overflow handling
  - FTP connection failures
  - Intermittent network buffering
  - Certificate error handling
  - Offline operation mode

**Run:**
```bash
pytest -m integration -v
```

### Performance Tests

**Location:** `tests/performance/`

**Coverage:**
- `test_load.py` - Performance and load testing (15 tests)
  - Thermal capture framerate (target: ≥3 FPS)
  - Data processing latency (target: <50ms avg)
  - MQTT publish throughput (target: ≥50 msg/sec)
  - Memory usage and leak detection
  - CPU usage monitoring
  - Local buffer read/write performance
  - 24-hour stability simulation
  - Concurrent operations
  - Multi-ROI processing scalability

**Run:**
```bash
# Run all performance tests
pytest -m performance -v

# Run fast performance tests only
pytest -m "performance and not slow" -v

# Run 24-hour simulation (slow)
pytest tests/performance/test_load.py::TestPerformance::test_24hour_stability_simulation -v
```

**Performance Targets:**
- Thermal capture: ≥3 FPS (4Hz sensor with overhead)
- Processing latency: <50ms average, <100ms P95
- MQTT throughput: ≥50 messages/second
- Memory increase: <50 MB over 1000 captures
- CPU usage: <50% average during normal operation
- Buffer writes: ≥100 writes/second
- Buffer reads: ≥50 reads/second

### Security Tests

**Location:** `tests/security/`

**Coverage:**
- `test_security.py` - Security validation (25+ tests)
  - No hardcoded credentials in config
  - Environment variable credential loading
  - Certificate file permissions (600)
  - AWS IoT certificate validation
  - No plaintext passwords in logs
  - MQTT TLS enforcement
  - S3 HTTPS enforcement
  - Web interface authentication
  - SQL injection prevention
  - Path traversal prevention
  - MQTT QoS levels for alerts
  - Secure random generation
  - Debug mode disabled in production

**Run:**
```bash
pytest -m security -v
```

## Test Fixtures

**Common fixtures** (defined in `conftest.py`):

- `mock_config` - Mock ConfigManager with test values
- `mock_aws_publisher` - Mock AWS IoT publisher
- `mock_ftp_publisher` - Mock FTP publisher
- `mock_local_buffer` - Mock local buffer
- `sample_thermal_frame` - Normal thermal frame (20-40°C)
- `hot_thermal_frame` - Thermal frame with hot spots (90-100°C)
- `sample_processed_data` - Processed data from DataProcessor
- `sample_alert_data` - Sample alert payload
- `temp_dir` - Temporary directory for test files

## Continuous Integration

### GitHub Actions

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-mock psutil

    - name: Run unit tests
      run: pytest -m unit --cov=src --cov-report=xml

    - name: Run integration tests
      run: pytest -m integration -v

    - name: Run security tests
      run: pytest -m security -v

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

Install pre-commit hook to run tests before commits:

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest -m "unit and not slow" -q
```

## Test Coverage

Generate coverage report:

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open coverage report
open htmlcov/index.html
```

**Coverage Targets:**
- Overall: ≥80%
- Core components (data_processor, data_uploader): ≥90%
- Critical paths (thermal capture, alert publishing): 100%

## Troubleshooting

### Import Errors

If you see import errors when running tests:

```bash
# Ensure src/ is in Python path
export PYTHONPATH="${PYTHONPATH}:/home/user/transformer-monitor/src"

# Or install package in development mode
pip install -e .
```

### Hardware-Dependent Tests Failing

Tests requiring hardware will fail on development machines. Skip them:

```bash
pytest -m "not requires_hardware"
```

### Slow Tests Taking Too Long

Skip slow tests during development:

```bash
pytest -m "not slow"
```

### Database Lock Errors

If you see database lock errors in parallel test runs:

```bash
# Run tests sequentially
pytest -n 1
```

### Mock Issues

If mocks aren't working as expected:

```bash
# Run tests with print output
pytest -s -v

# Check fixture usage
pytest --fixtures
```

## Writing New Tests

### Unit Test Template

```python
@pytest.mark.unit
class TestMyComponent:
    """Test MyComponent"""

    def test_initialization(self, mock_config):
        """Test component initializes correctly"""
        component = MyComponent(mock_config)
        assert component is not None

    def test_functionality(self, mock_config):
        """Test specific functionality"""
        component = MyComponent(mock_config)
        result = component.do_something()
        assert result is True
```

### Integration Test Template

```python
@pytest.mark.integration
class TestMyIntegration:
    """Test integration between components"""

    def test_end_to_end_flow(self, mock_config):
        """Test complete flow through system"""
        component_a = ComponentA(mock_config)
        component_b = ComponentB(mock_config)

        # Execute flow
        data = component_a.process()
        result = component_b.handle(data)

        assert result is True
```

### Performance Test Template

```python
@pytest.mark.performance
class TestMyPerformance:
    """Test performance characteristics"""

    def test_operation_latency(self):
        """Test operation completes within target latency"""
        component = MyComponent()

        start = time.time()
        component.expensive_operation()
        latency = (time.time() - start) * 1000  # ms

        assert latency < 100, f"Latency too high: {latency:.2f}ms"
```

## Best Practices

1. **Test Isolation** - Each test should be independent and not rely on other tests
2. **Mock External Dependencies** - Mock hardware, network, and file system when possible
3. **Clear Assertions** - Use descriptive assertion messages
4. **Test Edge Cases** - Test boundary conditions, empty inputs, error conditions
5. **Performance Baselines** - Update performance targets as system evolves
6. **Security First** - Always test security-critical paths
7. **Documentation** - Document test purpose and expected behavior

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

## Support

For questions or issues with tests:

1. Check this README
2. Review test output with `-v` flag
3. Check fixture definitions in `conftest.py`
4. Consult pytest documentation

## License

Same as main project license.
