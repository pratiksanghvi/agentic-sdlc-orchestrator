"""Guardrails applied to every file the implementation agent writes."""

from __future__ import annotations

import fnmatch
import re
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

from orchestrator.config.models import Stack

SUPPRESSION = re.compile(r"(nosemgrep|NOSONAR|pragma:\s*allowlist\s+secret|gitleaks:allow)",
                         re.IGNORECASE)


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def check_paths(paths: list[str], stack: Stack, forbidden: list[str]) -> list[str]:
    problems = []
    for path in paths:
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            problems.append(f"{path}: must be a relative path inside the workspace")
        elif _matches(path, forbidden):
            problems.append(f"{path}: writing here is forbidden by policy")
        elif not _matches(path, stack.path_allowlist):
            problems.append(f"{path}: not in the stack's path allowlist {stack.path_allowlist}")
    return problems


def check_suppressions(files: dict[str, str]) -> list[str]:
    return [f"{path}: contains a scanner-suppression marker" for path, text in files.items()
            if SUPPRESSION.search(text)]


def maven_dependencies(pom_xml: str) -> list[tuple[str, str | None]]:
    """(groupId:artifactId, version or None) for parent, dependencies and plugins."""
    root = ET.fromstring(pom_xml)
    ns = {"m": root.tag[1:].split("}")[0]} if root.tag.startswith("{") else {}
    prefix = "m:" if ns else ""

    def text(el, name):
        found = el.find(f"{prefix}{name}", ns)
        return found.text.strip() if found is not None and found.text else None

    coords = []
    parent = root.find(f"{prefix}parent", ns)
    if parent is not None:
        coords.append((f"{text(parent, 'groupId')}:{text(parent, 'artifactId')}",
                       text(parent, "version")))
    xpaths = (f".//{prefix}dependencies/{prefix}dependency", f".//{prefix}plugins/{prefix}plugin")
    for xpath in xpaths:
        for dep in root.findall(xpath, ns):
            group = text(dep, "groupId") or "org.apache.maven.plugins"
            coords.append((f"{group}:{text(dep, 'artifactId')}", text(dep, "version")))
    return coords


# build plugins that ship with Maven itself are always allowed
_MAVEN_CORE = re.compile(r"^org\.apache\.maven\.plugins:")


def check_maven_dependencies(pom_xml: str, stack: Stack) -> list[str]:
    try:
        coords = maven_dependencies(pom_xml)
    except ET.ParseError as exc:
        return [f"pom.xml is not valid XML: {exc}"]
    problems = []
    for coord, version in coords:
        if _MAVEN_CORE.match(coord):
            continue
        allowed = stack.dependencies.get(coord)
        if allowed is None:
            problems.append(f"pom.xml: dependency {coord} is not in the allowlist")
        elif allowed != "managed" and version not in (None, allowed):
            problems.append(f"pom.xml: {coord} must use version {allowed}, not {version}")
    return problems
