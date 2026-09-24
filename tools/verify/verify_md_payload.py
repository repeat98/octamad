#!/usr/bin/env python3
"""Verify the generated Machinedrum payload against md_replay's relocation."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "build"))
import md_payload  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(md_payload.verify())
