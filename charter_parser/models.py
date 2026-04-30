"""Domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Clause(BaseModel):
    """A single numbered clause of a charter party agreement."""

    id: str = Field(description="Clause identifier as printed (e.g. '1', '11', '20A').")
    title: str = Field(description="Heading of the clause; empty string if untitled.")
    text: str = Field(description="Verbatim body of the clause, with sub-clauses inline.")


class ClauseList(BaseModel):
    """Container used as the structured output of the LLM call."""

    clauses: list[Clause]
