"""
The Phase 4 agent: a LangGraph ReAct-style agent (reason -> call tool(s) ->
observe -> repeat -> final answer) built from the tools in tools.py.

Unlike Phase 3's /research/query (a fixed vector-then-graph pipeline
every query runs through), this agent decides per-query which tools are
relevant and how many rounds of tool calls it needs - a simple lookup
might take one call, "how did RAG evolve" might take four or five.

We use langchain.agents.create_agent (LangGraph's current recommended
entrypoint, built on langgraph.prebuilt under the hood) rather than
hand-rolling a StateGraph: it implements the same reason/act/observe
loop this project needs, is maintained upstream, and lets us focus on
the tools and prompt - the part that's actually specific to ResearchGraph.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain.agents import create_agent
from loguru import logger

from app.agent.llm_adapter import get_chat_model
from app.agent.tools import AGENT_TOOLS

SYSTEM_PROMPT = """You are the ResearchGraph agent, a research discovery assistant with tools \
over a knowledge graph (Neo4j) and a semantic search index (Qdrant) of academic papers.

Decide which tools are actually relevant to the user's question - do not call every tool \
"just in case". A simple lookup might need only one tool call; a question about how a \
research area evolved might need several, e.g.: search_papers to find the area, then \
find_foundational_papers and find_recent_papers for the relevant topic, then find_citations \
on a couple of key papers to see how they connect.

Rules:
- Only state facts that came from a tool result. Never invent paper titles, authors, years, \
or citation relationships.
- Topic-specific tools (find_topic_papers, find_foundational_papers, find_recent_papers) \
require an EXACT indexed topic name. If one returns no results, call list_topics to find \
the real name before giving up or guessing.
- When you reference a paper, include its paper_id in brackets, e.g. [W2741809807], so the \
answer is traceable to evidence.
- If the available tools cannot answer part of the question, say so directly rather than \
filling the gap with general/trained knowledge.
- Once you have enough evidence, give a clear, organized final answer - don't keep calling \
tools past the point of diminishing returns."""


@dataclass
class ToolCallRecord:
    tool: str
    input: dict
    output_preview: str


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    degraded: bool = False


def _extract_tool_trace(messages: list, max_preview_chars: int = 400) -> list[ToolCallRecord]:
    """
    Walk the agent's message history and pair each requested tool call
    (from an AIMessage.tool_calls entry) with the ToolMessage carrying
    its result, using the shared tool_call_id. This trace is what makes
    the agent's reasoning inspectable rather than a black box - the same
    explainability principle Phase 3 applied to retrieved_facts vs.
    interpretation.
    """
    pending: dict[str, dict] = {}
    trace: list[ToolCallRecord] = []

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for call in msg.tool_calls:
                pending[call["id"]] = {"tool": call["name"], "input": call["args"]}
        elif isinstance(msg, ToolMessage):
            call_info = pending.get(msg.tool_call_id)
            if call_info:
                preview = str(msg.content)
                if len(preview) > max_preview_chars:
                    preview = preview[:max_preview_chars] + "…"
                trace.append(ToolCallRecord(tool=call_info["tool"], input=call_info["input"], output_preview=preview))

    return trace


def _extract_final_text(final_message) -> str:
    """LangChain content can be a plain string or a list of content blocks depending on provider."""
    content = getattr(final_message, "content", "")
    if isinstance(content, list):
        return "".join(block.get("text", "") for block in content if isinstance(block, dict))
    return content or ""


def run_agent(query: str, recursion_limit: int = 12) -> AgentResult:
    try:
        model = get_chat_model()
    except Exception as e:
        logger.error(f"Agent LLM unavailable: {e}")
        return AgentResult(
            answer=(
                "The research agent needs an LLM provider configured (LLM_PROVIDER + API key "
                "in .env) to reason over tool calls. Phases 1-3 (search, graph, hybrid "
                "retrieval) work without one; the agent specifically needs tool-calling support."
            ),
            degraded=True,
        )

    agent = create_agent(model, AGENT_TOOLS, system_prompt=SYSTEM_PROMPT)

    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=query)]},
            config={"recursion_limit": recursion_limit},
        )
    except Exception as e:
        logger.error(f"Agent run failed: {e}")
        return AgentResult(answer=f"The research agent failed while running: {e}", degraded=True)

    messages = result.get("messages", [])
    tool_trace = _extract_tool_trace(messages)
    final_message = messages[-1] if messages else None
    answer = _extract_final_text(final_message) if final_message is not None else ""

    return AgentResult(answer=answer, tool_calls=tool_trace, degraded=False)
