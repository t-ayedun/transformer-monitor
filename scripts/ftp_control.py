#!/usr/bin/env python3
"""
FTP Control Utility
===================
Controls the FTP cold-storage service on the running Raspberry Pi by writing
to a persistent state file that the service reads at the start of every cycle.
Changes take effect immediately — NO service restart required.

State file location:
    /home/smartie/transformer_monitor_data/ftp_state.json

Usage:
    python ftp_control.py status              - Show current FTP state
    python ftp_control.py disable             - Pause all FTP uploads immediately
    python ftp_control.py enable              - Resume FTP uploads immediately
    python ftp_control.py interval <seconds>  - Change upload interval (e.g. 3600)
    python ftp_control.py reset               - Remove state file (revert to config defaults)

Examples:
    python ftp_control.py disable
    python ftp_control.py enable
    python ftp_control.py interval 3600       # Upload at most once per hour
    python ftp_control.py interval 86400      # Upload once per day
    python ftp_control.py status
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime

# ── State file path ─────────────────────────────────────────────────────────
STATE_FILE = Path('/home/smartie/transformer_monitor_data/ftp_state.json')

# Default state written when enabling for the first time (easy to re-enable)
DEFAULT_ENABLED_STATE = {
    "enabled": True,
    "upload_interval_seconds": 3600,   # 1 hour — conservative, avoids IP bans
    "note": "Managed by scripts/ftp_control.py. Edit carefully.",
    "last_modified": None
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _read_state() -> dict:
    """Read current state from file, or return a sensible default."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"WARNING: Could not parse state file: {e}")
    # No state file — FTP runs at whatever the config says
    return {"enabled": True, "note": "(no state file — service uses config defaults)"}


def _write_state(state: dict):
    """Write state to file, creating parent directories as needed."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state['last_modified'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    print(f"  State file written: {STATE_FILE}")


def _print_state(state: dict):
    enabled = state.get('enabled', True)
    interval = state.get('upload_interval_seconds', '(config default)')
    modified = state.get('last_modified', 'never')

    print("\n=== FTP Control State ===")
    print(f"  Status  : {'✅ ENABLED  (FTP running)' if enabled else '🚫 DISABLED (FTP paused)'}")
    print(f"  Interval: {interval}s  ({int(interval)//60} min)" if isinstance(interval, int) else f"  Interval: {interval}")
    print(f"  Modified: {modified}")
    if not STATE_FILE.exists():
        print("  (no state file on disk — service using config defaults)")
    print()


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_status():
    state = _read_state()
    _print_state(state)


def cmd_disable():
    state = _read_state()
    state['enabled'] = False
    if 'upload_interval_seconds' not in state:
        state['upload_interval_seconds'] = DEFAULT_ENABLED_STATE['upload_interval_seconds']
    _write_state(state)
    print("\n🚫 FTP uploads DISABLED.")
    print("   The running service will pause on its next cycle (within the current interval).")
    print("   To re-enable: python ftp_control.py enable\n")


def cmd_enable():
    # Build a clean enabled state, preserving existing interval if set
    existing = _read_state()
    state = {**DEFAULT_ENABLED_STATE}
    state['enabled'] = True
    if 'upload_interval_seconds' in existing and isinstance(existing['upload_interval_seconds'], int):
        state['upload_interval_seconds'] = existing['upload_interval_seconds']
    _write_state(state)
    print("\n✅ FTP uploads ENABLED.")
    print("   The running service will resume on its next cycle.")
    print(f"   Upload interval: {state['upload_interval_seconds']}s ({state['upload_interval_seconds']//60} min)\n")


def cmd_interval(seconds_str: str):
    try:
        seconds = int(seconds_str)
        if seconds < 60:
            print("ERROR: Interval must be at least 60 seconds (to avoid hammering the server).")
            sys.exit(1)
    except ValueError:
        print(f"ERROR: '{seconds_str}' is not a valid number of seconds.")
        sys.exit(1)

    state = _read_state()
    old_interval = state.get('upload_interval_seconds', '(config default)')
    state['upload_interval_seconds'] = seconds
    _write_state(state)

    print(f"\n⏱  Upload interval changed: {old_interval}s → {seconds}s ({seconds//60} min)")
    print("   Takes effect on the running service within the current cycle.\n")


def cmd_reset():
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print(f"\n🔄 State file removed: {STATE_FILE}")
        print("   The service will revert to settings in site_config.yaml on its next cycle.\n")
    else:
        print("\nNothing to reset — no state file exists.\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'status':
        cmd_status()
    elif command == 'disable':
        cmd_disable()
    elif command == 'enable':
        cmd_enable()
    elif command == 'interval':
        if len(sys.argv) < 3:
            print("ERROR: Please provide interval in seconds.")
            print("  Example: python ftp_control.py interval 3600")
            sys.exit(1)
        cmd_interval(sys.argv[2])
    elif command == 'reset':
        cmd_reset()
    else:
        print(f"ERROR: Unknown command '{command}'")
        print("Valid commands: status, disable, enable, interval, reset")
        sys.exit(1)


if __name__ == '__main__':
    main()
