"""
Phase 4 - the agent decides which tools to call, unlike Phase 3's
/research/query which always runs the same vector-then-graph pipeline.
Use this endpoint for open-ended or multi-step questions ("how did RAG
research evolve", "who works on X and what have they written recently");
use /research/query when you specifically want the fixed hybrid-fusion
behavior with guaranteed vector+graph evidence every time.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agent.graph import run_agent
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse, ToolCallOut

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(request: AgentQueryRequest):
    try:
        result = run_agent(request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent query failed: {e}")

    tool_calls = [ToolCallOut(tool=tc.tool, input=tc.input, output_preview=tc.output_preview) for tc in result.tool_calls]
    tools_used = list(dict.fromkeys(tc.tool for tc in result.tool_calls))  # de-duplicated, order-preserved

    return AgentQueryResponse(
        query=request.query,
        answer=result.answer,
        tool_calls=tool_calls,
        tools_used=tools_used,
        degraded=result.degraded,
    )
