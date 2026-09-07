#!/usr/bin/env python3
"""Frozen leading-comment boundary experiment using the established rig."""
import e51_run as rig

rig.ARMS = {"baseline": [], "flag-off": [], "leading-comments": ["--leading-comments"]}
rig.ISOLATE_BLOCK_CACHE = True

if __name__ == "__main__":
    rig.main()
