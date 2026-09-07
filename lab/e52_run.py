#!/usr/bin/env python3
"""E52 uses E51's frozen evaluator/private-clone rig with two new arms."""
import e51_run as run

run.ARMS = {
    "baseline": [],
    "flag-off": [],
    "unique-budget": ["--unique-span-budget"],
    "wide-unique-budget": ["--unique-span-budget", "--symbol-graph", "--max-additions", "32"],
}

if __name__ == "__main__":
    run.main()
