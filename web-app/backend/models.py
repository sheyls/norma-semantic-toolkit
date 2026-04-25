from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class PackSummary(BaseModel):
    name: str
    rule_count: int
    has_abox: bool
    has_swrl: bool
    can_rebuild: bool = False


class EntityUpdateRequest(BaseModel):
    action: str
    field: Optional[str] = None
    label_a: Optional[str] = None
    label_b: Optional[str] = None
    canonical: Optional[str] = None
    label: Optional[str] = None


class UploadSummary(BaseModel):
    pack: str
    rules_count: int
    has_abox: bool
    has_swrl: bool


JSONDict = dict[str, Any]
