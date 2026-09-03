"""Read only exported dashboard artifacts; never import or read the sealed oracle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from blindspot.contracts import IntegrityError

ALLOWED_FILES = frozenset(
    {
        "manifest.json",
        "public.json",
        "benchmark.json",
        "observations.json",
        "reliability.json",
        "reliability_benchmark.json",
    }
)


def read_artifact(directory: str | Path, filename: str) -> dict:
    """Verify byte integrity before reading a fixed allowlisted aggregate artifact."""

    if filename not in ALLOWED_FILES:
        raise IntegrityError("dashboard cannot read that artifact")
    root = Path(directory)
    checksums = json.loads((root / "checksums.json").read_text())
    payload = (root / filename).read_bytes()
    if hashlib.sha256(payload).hexdigest() != checksums.get(filename):
        raise IntegrityError(f"Artifact hash mismatch: {filename}")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise IntegrityError("expected an object artifact")
    return parsed


def read_reliability(directory: str | Path, source_directory: str | Path) -> dict:
    """Bind aggregate sensitivity evidence to the exact original source manifest."""

    artifact = read_artifact(directory, "reliability.json")
    source = read_artifact(source_directory, "manifest.json")
    digest = hashlib.sha256((Path(source_directory) / "manifest.json").read_bytes()).hexdigest()
    design = artifact["design"]
    if (
        design["source_run_id"] != source["run_id"]
        or design["source_hashes"]["manifest.json"] != digest
    ):
        raise IntegrityError("reliability evidence belongs to a different source run")
    return artifact
