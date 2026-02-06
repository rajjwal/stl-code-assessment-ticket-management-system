"""Pydantic schemas for the natural language query endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AskRequest(BaseModel):
    """Request body for natural language CMDB queries."""

    question: str


class AskResponse(BaseModel):
    """Response from a natural language CMDB query."""

    answer: str
    results: list[dict[str, Any]] = []
    query_interpretation: str = ""  # Shows how the AI interpreted the question
