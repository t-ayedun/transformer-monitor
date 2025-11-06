# Thermal Camera Calibration Procedure

## Why Calibrate?

Thermal cameras can have measurement errors due to:
- Sensor tolerances
- Environmental factors
- Distance and angle to target
- Emissivity differences

Calibration ensures accurate temperature readings by comparing against a known reference.

## Equipment Needed

1. **Contact thermometer** (one of):
   - Infrared thermometer (non-contact)
   - K-type thermocouple probe
   - RTD sensor

2. **Access to transformer** at various temperatures

3. **Stable conditions**:
   - No direct sunlight on measurement area
   - Minimal wind
   - Transformer under steady load

## Calibration Process

### Step 1: Prepare
```bash
# SSH into device
balena ssh <device-uuid>

# Run calibration tool
python3 /app/scripts/calibration.py --interactive --measurements 3
```

### Step 2: Take Measurements

For best results, take measurements at 3 different temperatures:

1. **Low temperature** (~40-50°C):
   - Transformer at minimal load
   - Early morning or cool day

2. **Medium temperature** (~60-70°C):
   - Normal operating load
   - Typical conditions

3. **High temperature** (~80-90°C):
   - Peak load conditions
   - Hot day or maximum load test

### Step 3: Measurement Procedure

For each calibration point:

1. **Position contact thermometer**:
   - Place on transformer surface
   - Ensure good contact (for probe types)
   - Wait 30 seconds for stabilization

2. **Record reference temperature**:
   - Read contact thermometer
   - Enter value when prompted

3. **Camera captures thermal data**:
   - Tool automatically takes 10 samples
   - Averages readings
   - Calculates difference

4. **Repeat for all points**

### Step 4: Calculate Calibration

Tool automatically:
- Performs linear regression
- Calculates offset and multiplier
- Verifies accuracy across all points

Expected output:
```
CALIBRATION RESULTS
==================================================
Offset:     +2.35°C
Multiplier: 0.9823

Corrected formula:
  T_actual = 0.9823 * T_measured +2.35
```

### Step 5: Apply Calibration

Tool prompts to save to configuration:
```yaml
thermal_camera:
  calibration:
    enabled: true
    offset: 2.35
    multiplier: 0.9823
```

Restart application:
```bash
balena restart <device-uuid>
```

## Validation

After calibration, verify accuracy:

1. Take new contact measurement
2. Compare with thermal reading
3. Error should be < ±2°C

## Best Practices

### Do:
✓ Calibrate at site conditions
✓ Use multiple temperature points
✓ Ensure stable measurements
✓ Repeat if error > 2°C
✓ Recalibrate annually

### Don't:
✗ Calibrate in direct sunlight
✗ Use only one temperature point
✗ Rush measurements
✗ Ignore large discrepancies
✗ Calibrate during rain/fog

## Troubleshooting

**Large discrepancies (>5°C)**:
- Check emissivity setting
- Verify camera angle/distance
- Clean thermal camera lens
- Check contact thermometer battery

**Inconsistent readings**:
- Allow more stabilization time
- Reduce wind exposure
- Check transformer load is steady

**Can't achieve good calibration**:
- May need to replace thermal camera
- Check for condensation on lens
- Verify mounting is secure

## Emissivity Reference

Common materials on transformers:

| Material | Emissivity |
|----------|------------|
| Transformer oil | 0.95 |
| Painted steel tank | 0.90 - 0.95 |
| Bare steel | 0.70 - 0.85 |
| Aluminum | 0.05 - 0.15 |
| Porcelain bushings | 0.85 - 0.95 |
| Copper connections | 0.05 - 0.15 |

Adjust per-ROI if measuring different materials.