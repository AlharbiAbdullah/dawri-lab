#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "apache-ossie @ git+https://github.com/apache/ossie@adfa9e4#subdirectory=python",
#     "pyyaml",
# ]
# ///
"""Validate an Ossie document and print a one-line summary of it."""

import sys
from pathlib import Path

import yaml
from ossie.models import OssieDocument  # ty: ignore[unresolved-import]


def summarize(path: Path) -> str:
    raw = yaml.safe_load(path.read_text())
    doc = OssieDocument.model_validate(raw)
    relationships = doc.relationships or []
    return (
        f"{doc.name} {doc.version}: {len(doc.datasets)} datasets, "
        f"{len(relationships)} relationships, {len(doc.metrics)} metrics"
    )


if __name__ == "__main__":
    print(summarize(Path(sys.argv[1])))
