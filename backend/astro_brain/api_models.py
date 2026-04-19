"""Pydantic models for the public REST API wire format.

These are validated by FastAPI on incoming requests; any constraint
violation produces a 422 response with a machine-readable error body
before the route handler is called.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SlewRequest(BaseModel):
    """Body of ``POST /slew``."""

    axis: Literal["alt", "az"]
    direction: Literal["+", "-"]
    rate: int = Field(ge=1, le=9)


class StopRequest(BaseModel):
    """Body of ``POST /stop``. Omitting ``axis`` stops every active slew."""

    axis: Literal["alt", "az"] | None = None


class TrackingRequest(BaseModel):
    """Body of ``POST /tracking``."""

    enabled: bool


class OkResponse(BaseModel):
    """Generic 200 response for commands that have no payload."""

    ok: Literal[True] = True
