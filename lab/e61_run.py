#!/usr/bin/env python3
"""Frozen exact shared-source packing experiment."""
import e51_run as rig

rig.ARMS = {"baseline": [], "flag-off": [], "shared-source": ["--shared-source"]}
rig.ISOLATE_BLOCK_CACHE = True

if __name__ == "__main__":
    rig.main()
