#!/usr/bin/env python3
"""Validate the deterministic incident catalog without executing faults."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_CATEGORIES = {"resource", "network", "datastore", "deployment", "traffic"}


def main() -> int:
    path = Path(__file__).parents[1] / "data" / "scenarios" / "catalog.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    scenarios = document.get("scenarios", [])
    errors: list[str] = []

    if document.get("schema_version") != "incident-catalog.v1":
        errors.append("schema_version must be incident-catalog.v1")
    if len(scenarios) != 25:
        errors.append(f"expected 25 scenarios, found {len(scenarios)}")
    ids = [item.get("id") for item in scenarios]
    if len(set(ids)) != len(ids):
        errors.append("scenario IDs must be unique")
    roots = [item.get("root_cause") for item in scenarios]
    if len(set(roots)) != len(roots):
        errors.append("root causes must be unique")
    seeds = [item.get("seed") for item in scenarios]
    if len(set(seeds)) != len(seeds):
        errors.append("seeds must be unique")
    categories = {item.get("category") for item in scenarios}
    if categories != REQUIRED_CATEGORIES:
        errors.append(f"categories must be exactly {sorted(REQUIRED_CATEGORIES)}")
    for item in scenarios:
        required = ("target_service", "namespace", "expected_affected_services", "remediation", "cleanup")
        missing = [field for field in required if not item.get(field)]
        if missing:
            errors.append(f"{item.get('id', '<unknown>')} missing {', '.join(missing)}")
        if item.get("requires_ui") is not False:
            errors.append(f"{item.get('id', '<unknown>')} must not require UI changes")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: 25 deterministic scenarios across 5 categories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
