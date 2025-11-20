# Dashboard UI/UX Redesign Plan

## Current State Analysis

### Existing Components
1. **Alert Banner** - Configuration notice
2. **Status Bar** - 4 status items (thermal, visual, update, temp)
3. **Video Feeds** - 3 equal-sized cards (thermal, visual, fusion)
4. **Quick Actions** - Small card with 3 buttons
5. **System Info** - Full-width info grid
6. **ROI List** - Full-width ROI configurations

### Problems Identified
- ❌ No clear visual hierarchy - everything looks equally important
- ❌ Thermal feed (most critical) same size as others
- ❌ Status bar is functional but not visually engaging
- ❌ No real-time data visualization or trends
- ❌ ROI section is just text - not visual/scannable
- ❌ Quick actions isolated in small card
- ❌ Missing key operational metrics
- ❌ Layout doesn't guide user's attention effectively

---

## Proposed Redesign

### 1. Layout Structure: **Hero + Sidebar Pattern**

```
┌─────────────────────────────────────────────────────────┐
│ [SITE ID]                    [Quick Actions Toolbar]    │
├────────────────────────────────┬────────────────────────┤
│                                │  ┌──────────────────┐  │
│                                │  │  Visual Feed     │  │
│     THERMAL CAMERA             │  │  (Small)         │  │
│     (Large - Primary Focus)    │  └──────────────────┘  │
│                                │  ┌──────────────────┐  │
│     [Live temp overlays]       │  │  Fusion Feed     │  │
│                                │  │  (Small)         │  │
│                                │  └──────────────────┘  │
├────────────────────────────────┴────────────────────────┤
│  [Status Cards: 4-column grid]                          │
│  Camera | Temperature | System | Connectivity            │
├────────────────────────────────┬────────────────────────┤
│  Temperature Metrics           │  Active ROIs           │
│  ┌──────┬──────┬──────┐       │  ┌──────────────────┐  │
│  │ Min  │ Max  │ Avg  │       │  │ ROI 1  [OK]      │  │
│  └──────┴──────┴──────┘       │  │ ROI 2  [WARN]    │  │
│  [Mini trend chart]            │  │ ROI 3  [OK]      │  │
│                                │  └──────────────────┘  │
├────────────────────────────────┴────────────────────────┤
│  System Health & Recent Activity                        │
└─────────────────────────────────────────────────────────┘
```

### 2. Component Improvements

#### **A. Hero Thermal Feed (Primary)**
- **Size**: 60% of viewport width, prominent placement
- **Features**:
  - Live MJPEG stream
  - Temperature range overlay (gradient scale)
  - Hotspot indicators
  - ROI outlines with labels
  - Current timestamp
  - Recording indicator (if active)
- **Visual**: Larger, more prominent, clear focus

#### **B. Secondary Feeds Sidebar**
- **Layout**: Vertical stack on right side
- **Size**: Smaller than thermal, but visible
- **Features**:
  - Visual camera (top)
  - Fusion view (bottom)
  - Compact but clear
  - Toggle to swap positions or expand

#### **C. Enhanced Status Cards**
Replace simple status bar with **4 rich status cards**:

1. **Camera Status**
   - Thermal: Online/Offline with indicator
   - Visual: Online/Offline with indicator
   - Frame rate (FPS)
   - Resolution info
   - Icon: Camera symbol

2. **Temperature Status**
   - Current ambient temp
   - Min/Max today
   - Range indicator
   - Visual temp gauge
   - Icon: Thermometer

3. **System Health**
   - CPU/Memory usage
   - Uptime
   - Storage available
   - Icon: Server/Chip

4. **Connectivity**
   - AWS connection status
   - Last sync time
   - Network status
   - Icon: Cloud/Signal

#### **D. Temperature Metrics Dashboard**
- **3-column stat cards**: Min | Max | Average
- **Visual representation**:
  - Color-coded values (blue=cold, red=hot)
  - Trend arrows (↑↓→)
  - Comparison to threshold
- **Mini trend chart**: Last 10 readings (simple line chart)
- **Time range selector**: 1h | 6h | 24h

#### **E. Active ROIs Panel**
Replace text list with **visual ROI cards**:
```
┌─────────────────────────────┐
│ Top Coil        [75.2°C] ✓ │  <- Green for OK
│ Warning: 80°C  Critical: 90°C│
│ ▓▓▓▓▓░░░░░ (83% of critical) │
├─────────────────────────────┤
│ Bottom Coil    [85.8°C] ⚠  │  <- Yellow for Warning
│ Warning: 80°C  Critical: 90°C│
│ ▓▓▓▓▓▓▓▓░░ (95% of critical) │
└─────────────────────────────┘
```

Features:
- Status indicator (✓ OK, ⚠ Warning, 🔴 Critical)
- Current temperature (large, bold)
- Progress bar to threshold
- Color coding by status
- Click to jump to ROI mapper

#### **F. Quick Actions Toolbar**
Move from card to **fixed toolbar** at top-right:
```
[Snapshot] [ROI Mapper] [Refresh] [•••]
```
- Always visible
- Icon + text buttons
- Hover tooltips
- Dropdown for more actions (•••)

#### **G. System Health Footer**
Compact status bar at bottom:
```
Site: TEST_SITE | Uptime: 2d 14h | Last AWS Sync: 2 min ago | Storage: 45% | Ver: 1.0.0
```

### 3. Visual Design Enhancements

#### **Color Coding System**
- **Green (#00ba7c)**: Normal/OK status
- **Yellow (#ffd400)**: Warning state
- **Red (#f4212e)**: Critical/Error
- **Blue (#1d9bf0)**: Info/Action
- **Gray (#8b98a5)**: Inactive/Disabled

#### **Typography**
- **Headers**: 1.25rem, weight 700
- **Body**: 0.9rem, weight 400
- **Labels**: 0.75rem, weight 600, uppercase, tracking
- **Metrics**: 1.5-2rem, weight 700, tabular numbers

#### **Spacing & Layout**
- **Consistent gaps**: 1.5rem between major sections
- **Card padding**: 1.5rem
- **Border radius**: 16px for cards, 8px for elements
- **Shadows**: Subtle, elevation-based

#### **Animations**
- **Status changes**: Smooth color transitions (200ms)
- **New data**: Subtle pulse on update
- **Hover states**: Scale 1.02, border color change
- **Loading**: Skeleton screens, not spinners

### 4. Responsiveness

#### **Desktop (>1200px)**
- Full hero layout as described
- All panels visible
- 3-column metrics

#### **Tablet (768-1200px)**
- Stack secondary feeds below hero
- 2-column metrics
- Maintain visual hierarchy

#### **Mobile (<768px)**
- Single column
- Thermal feed full-width
- Collapsible sections
- Swipe between feeds

### 5. Information Hierarchy (Priority Order)

1. **Primary**: Thermal feed + live temp
2. **Secondary**: Status cards (health at a glance)
3. **Tertiary**: ROI status (detailed monitoring)
4. **Supporting**: Metrics, trends, system info
5. **Utility**: Actions, navigation, settings

---

## Implementation Phases

### **Phase 1: Layout Restructure** ⭐
- Hero + sidebar layout
- Status cards redesign
- Visual hierarchy
- Quick actions toolbar

### **Phase 2: Enhanced Visuals**
- Temperature metrics dashboard
- ROI visual cards
- Color coding system
- Icons and indicators

### **Phase 3: Data Visualization**
- Mini trend charts
- Progress bars
- Real-time updates
- Animation polish

### **Phase 4: Responsive & Polish**
- Mobile optimization
- Loading states
- Error handling
- Accessibility

---

## Success Metrics

✅ **User can identify system status in <3 seconds**
✅ **Critical alerts immediately visible**
✅ **Clear visual hierarchy guides attention**
✅ **Professional, modern appearance**
✅ **Information is scannable, not buried**
✅ **Actions are discoverable and accessible**

---

## Next Steps

1. **Review this plan** - Approve overall direction
2. **Prioritize features** - What's most important?
3. **Mockup approval** - Visual design confirmation
4. **Implementation** - Build in phases
5. **Testing** - Validate with actual data

---

## Questions to Consider

1. Do you want **real-time charts** (temperature over time)?
2. Should we add **alert history** panel?
3. Need **export/report** functionality?
4. Want **customizable dashboard** (user can arrange panels)?
5. Add **notifications** (toast messages for events)?

