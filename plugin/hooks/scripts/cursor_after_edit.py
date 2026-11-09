#!/usr/bin/env python3
"""Cursor afterFileEdit hook. Cursor sends {"file_path": ..., "edits": [...]} on stdin; this runs the same
pattern scan as the Claude Code hook (scan_edit.py) and prints what belongs in the platform, not in code.
Cursor shows the output to the agent. Exit 0 always; a hook must never block an edit."""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import scan_edit
except ImportError:
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    path = payload.get("file_path") or payload.get("filePath") or ""
    if not path:
        return
    # Reuse the Claude Code hook by giving it the shape it expects.
    sys.stdin = type("S", (), {"read": lambda self: json.dumps({"tool_input": {"file_path": path}})})()
    try:
        scan_edit.main()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    try:
        main()
    finally:
        sys.exit(0)
