"""Seeded, reproducible load-profile definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProfileName = Literal["baseline", "burst", "checkout-heavy", "degradation"]


@dataclass(frozen=True)
class LoadProfile:
    name: ProfileName
    seed: int
    duration_seconds: int
    requests_per_second: int
    checkout_ratio: float
    error_injection: str | None = None


PROFILES: dict[ProfileName, LoadProfile] = {
    "baseline": LoadProfile("baseline", 1001, 300, 10, 0.10),
    "burst": LoadProfile("burst", 1002, 180, 50, 0.15),
    "checkout-heavy": LoadProfile("checkout-heavy", 1003, 300, 20, 0.70),
    "degradation": LoadProfile("degradation", 1004, 300, 20, 0.40, "dependency-latency"),
}


def get_profile(name: ProfileName) -> LoadProfile:
    """Return a pinned profile; callers must not mutate the shared definition."""
    return PROFILES[name]


def request_count(profile: LoadProfile) -> int:
    return profile.duration_seconds * profile.requests_per_second


def expected_checkout_count(profile: LoadProfile) -> int:
    return round(request_count(profile) * profile.checkout_ratio)
