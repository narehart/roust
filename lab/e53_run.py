#!/usr/bin/env python3
"""Frozen emitted-coverage experiments with independent per-arm block caches."""
import e51_run as runner
runner.ISOLATE_BLOCK_CACHE = True
runner.ARMS = {
    'baseline': [],
    'flag-off': [],
    'emitted': ['--emitted-coverage'],
    'emitted-shape': ['--emitted-coverage', '--shape-union-blocks'],
}
if __name__ == '__main__':
    runner.main()
