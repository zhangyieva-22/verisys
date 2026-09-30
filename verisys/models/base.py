"""Shared schema configuration; no execution or judgment behavior."""
from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
