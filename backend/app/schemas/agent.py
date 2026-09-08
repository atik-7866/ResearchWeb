from __future__ import annotations

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural language research question")


class ToolCallOut(BaseModel):
    tool: str
    input: dict
    output_preview: str = Field(
        description="Truncated tool result shown for transparency - the agent saw the full result."
    )


class AgentQueryResponse(BaseModel):
    query: str
    answer: str
    tool_calls: list[ToolCallOut] = Field(
        default_factory=list,
        description="The full trace of which tools the agent chose to call, in order, and what each returned.",
    )
    tools_used: list[str] = Field(default_factory=list)
    degraded: bool = Field(
        default=False, description="True if no LLM provider is configured or the agent run failed"
    )
