"""Read the committed Ossie document. Shared by the generators in scripts/."""

from pathlib import Path

import yaml
from ossie.models import (  # ty: ignore[unresolved-import]
    OssieDataset,
    OssieDocument,
    OssieExpression,
)

SOURCE = Path("semantic/dawri.ossie.yaml")


def load(path: Path = SOURCE) -> OssieDocument:
    return OssieDocument.model_validate(yaml.safe_load(path.read_text()))


def ansi_sql(expression: OssieExpression) -> str:
    for d in expression.dialects:
        if d.dialect == "ANSI_SQL":
            return d.expression
    raise SystemExit(f"no ANSI_SQL dialect in {expression!r}")


def dataset(doc: OssieDocument, name: str) -> OssieDataset:
    for d in doc.datasets:
        if d.name == name:
            return d
    raise SystemExit(f"no dataset {name} in the Ossie document")


def table_name(ds: OssieDataset) -> str:
    return ds.source.split(".")[-1].strip('"')
