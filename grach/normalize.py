from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grach.schema import EntityType

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def canonical_name(name: str) -> str:
    separated = _CAMEL_BOUNDARY.sub(" ", name.strip())
    return " ".join(separated.replace("_", " ").replace("-", " ").lower().split())


def slug(name: str) -> str:
    return _NON_WORD.sub("-", canonical_name(name)).strip("-")


def entity_id(entity_type: EntityType, name: str) -> str:
    return f"{entity_type.lower()}:{slug(name)}"
