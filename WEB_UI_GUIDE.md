# Web UI Guide - Current Status

## Pages Available

After pulling latest changes, you should have these pages:

### 1. **Dashboard** - `http://localhost:5000/`
- Main monitoring view
- Live thermal, visual, and fusion camera streams
- Real-time ROI temperature overlays
- System status

### 2. **Smart ROI Mapper** - `http://localhost:5000/smart-roi-mapper`
- **NEW**: Thermal-native ROI mapping (no camera alignment needed)
- Manual mode: Click & drag thermal cells
- Auto mode: AI detects hotspots automatically
- Works directly on 32×24 thermal grid
- **This replaces the old visual-based mapper**

### 3. **Heatmap Validation** - `http://localhost:5000/thermal-heatmap`
- View exact temperatures for all pixels
- Progressive zoom: 4×3, 8×6, 16×12, 32×24
- Validate thermal accuracy
- Real-time statistics

### 4. **Old Pages** (Still exist but not needed):
- `/roi-mapper` - Old visual-based mapper (impractical, deprecated)
- `/camera-alignment` - Not needed with new thermal-native approach

## Current Issues to Fix

Based on your feedback:

1. **Navigation cleanup**: Remove duplicate links
2. **Remove emojis**: Too many, unprofessional
3. **Dark theme**: Apply X.com-style dark background
4. **Better fonts**: Improve typography
5. **Consistency**: All pages should look similar

## What You Should Test

1. Pull latest code:
   ```bash
   git pull origin claude/stop-running-process-018nR6UUhQKP9WCMC9TiRjnj
   ```

2. Restart application:
   ```bash
   python src/main.py
   ```

3. Open browser:
   - Go to `http://localhost:5000/`
   - Check dashboard loads
   - Click to Smart ROI Mapper
   - Click to Heatmap
   - Verify all pages load

4. Report back:
   - What do you see?
   - Any errors?
   - What looks wrong?

## Next Steps

I will now:
1. Apply consistent dark theme (like X.com) to all pages
2. Remove all emojis
3. Fix duplicate navigation links
4. Better typography
5. Make everything professional

Tell me what you're currently seeing and I'll fix it properly.
