#!/usr/bin/env python3
"""Frozen query-local feedback experiment, with independent block caches."""
import e51_run as runner
runner.ISOLATE_BLOCK_CACHE = True
runner.DISCOVERY_ENDPOINTS = 3
runner.ARMS = {
    'baseline': [],
    'flag-off': [],
    'local-feedback': ['--local-feedback'],
}
if __name__ == '__main__':
    runner.main()
