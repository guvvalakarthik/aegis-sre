"""Validate the local tools required to develop AegisSRE."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Requirement:
    command: str
    minimum: tuple[int, ...]
    version_args: tuple[str, ...]
    label: str


REQUIREMENTS = (
    Requirement("python", (3, 12), ("--version",), "Python"),
    Requirement("git", (2, 40), ("--version",), "Git"),
    Requirement("docker", (24, 0), ("--version",), "Docker"),
    Requirement("kubectl", (1, 28), ("version", "--client", "--output=yaml"), "kubectl"),
    Requirement("helm", (3, 14), ("version", "--short"), "Helm"),
    Requirement("node", (20, 0), ("--version",), "Node.js"),
)


def version_from(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(?:v|version\\s*)?(\\d+)(?:\\.(\\d+))?(?:\\.(\\d+))?", text, re.I)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def run(command: str, args: Sequence[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            [command, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def check_requirement(requirement: Requirement) -> bool:
    path = shutil.which(requirement.command)
    if path is None:
        print(f"FAIL {requirement.label}: '{requirement.command}' was not found on PATH")
        return False

    code, output = run(path, requirement.version_args)
    detected = version_from(output)
    if code != 0 or detected is None:
        print(f"FAIL {requirement.label}: could not read version ({output})")
        return False
    if detected < requirement.minimum:
        minimum = ".".join(map(str, requirement.minimum))
        actual = ".".join(map(str, detected))
        print(f"FAIL {requirement.label}: {actual} is below required {minimum}")
        return False

    print(f"PASS {requirement.label}: {'.'.join(map(str, detected))}")
    return True


def check_docker_resources() -> bool:
    if shutil.which("docker") is None:
        return False
    code, output = run("docker", ("info", "--format", "{{.NCPU}} {{.MemTotal}}"))
    if code != 0:
        print("FAIL Docker daemon: unavailable; start Docker Desktop or dockerd")
        return False
    parts = output.split()
    if len(parts) != 2:
        print("FAIL Docker resources: Docker returned an unreadable resource summary")
        return False
    cpus, memory = int(parts[0]), int(parts[1])
    minimum_gib = int(os.getenv("AEGIS_MIN_DOCKER_MEMORY_GIB", "4"))
    if cpus < 2 or memory < minimum_gib * 1024**3:
        print(
            f"FAIL Docker resources: need at least 2 CPUs and {minimum_gib} GiB; "
            f"found {cpus} CPUs and {memory / 1024**3:.1f} GiB"
        )
        return False
    print(f"PASS Docker resources: {cpus} CPUs, {memory / 1024**3:.1f} GiB")
    return True


def check_kubernetes_context() -> bool:
    if shutil.which("kubectl") is None:
        return False
    code, context = run("kubectl", ("config", "current-context"))
    if code != 0 or not context:
        print("FAIL Kubernetes context: no current context is configured")
        return False
    production = re.search(r"(?:^|[-_])(prod|production)(?:$|[-_])", context, re.I)
    if production and os.getenv("AEGIS_ALLOW_PRODUCTION_CONTEXT") != "1":
        print(
            f"FAIL Kubernetes context: '{context}' looks like production; "
            "set AEGIS_ALLOW_PRODUCTION_CONTEXT=1 only after an explicit review"
        )
        return False
    print(f"PASS Kubernetes context: {context}")
    return True


def main() -> int:
    failures = [not check_requirement(requirement) for requirement in REQUIREMENTS]
    failures.extend((not check_docker_resources(), not check_kubernetes_context()))
    if any(failures):
        print("Toolchain check failed. Fix the messages above and run it again.")
        return 1
    print("Toolchain check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
