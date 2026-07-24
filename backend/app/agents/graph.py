from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import langchain_agents
from app.agents import runner as agent_runner
from app.agents import tools as repo_tools
from app.agents.llm import use_mock


class LoopState(TypedDict, total=False):
    objective: str
    constraints: str
    criteria: List[str]
    criteria_raw: str
    plan: str
    steps: List[str]
    attempt: int
    max_attempts: int
    feedback: str
    files_changed: List[Dict[str, Any]]
    command_result: Dict[str, Any]
    validation_passed: bool
    validation_evidence: str
    validation_summary: str
    gate_approved: bool
    status: str
    logs: List[str]
    model: Optional[str]
    instructions: Optional[Dict[str, str]]
    scope_note: str


# -----------------------------------------------------------------------------
# LangGraph Node Handlers
# -----------------------------------------------------------------------------

def node_success_criteria(state: LoopState) -> Dict[str, Any]:
    """LangGraph node for Success Criteria Agent."""
    logs = list(state.get("logs", []))
    logs.append("[LangGraph:Node] Executing Success Criteria Agent")

    inst = (state.get("instructions") or {}).get("criteria")
    res = agent_runner.generate_success_criteria(
        objective=state.get("objective", ""),
        constraints=state.get("constraints", ""),
        instructions=inst,
        model=state.get("model"),
    )

    return {
        "criteria": res.get("criteria", []),
        "criteria_raw": res.get("raw", ""),
        "status": "CRITERIA_GENERATED",
        "logs": logs,
    }


def node_planning(state: LoopState) -> Dict[str, Any]:
    """LangGraph node for Planning Agent."""
    logs = list(state.get("logs", []))
    attempt = state.get("attempt", 1)
    logs.append(f"[LangGraph:Node] Executing Planning Agent (Attempt {attempt})")

    inst = (state.get("instructions") or {}).get("planning")
    res = agent_runner.generate_plan(
        objective=state.get("objective", ""),
        constraints=state.get("constraints", ""),
        criteria=state.get("criteria", []),
        feedback=state.get("feedback"),
        instructions=inst,
        model=state.get("model"),
    )

    return {
        "plan": res.get("plan", ""),
        "steps": res.get("steps", []),
        "status": "PLAN_GENERATED",
        "logs": logs,
    }


def node_execution(state: LoopState) -> Dict[str, Any]:
    """LangGraph node for Execution Agent."""
    logs = list(state.get("logs", []))
    attempt = state.get("attempt", 1)
    logs.append(f"[LangGraph:Node] Executing Execution Agent (Attempt {attempt})")

    inst = (state.get("instructions") or {}).get("execution")
    # For mock mode attempt 1, force fail if configured
    force_fail = use_mock() and attempt == 1

    res = agent_runner.execute_changes(
        objective=state.get("objective", ""),
        plan=state.get("plan", ""),
        criteria=state.get("criteria", []),
        feedback=state.get("feedback"),
        instructions=inst,
        model=state.get("model"),
        force_fail=force_fail,
    )

    files_raw = [
        f.model_dump() if hasattr(f, "model_dump") else dict(f)
        for f in res.get("filesChanged", [])
    ]

    return {
        "files_changed": files_raw,
        "status": "CHANGES_EXECUTED",
        "logs": logs + [f"[LangGraph:Exec] {t}" for t in res.get("transcript", [])],
    }


def node_validation(state: LoopState) -> Dict[str, Any]:
    """LangGraph node for Validation Agent."""
    logs = list(state.get("logs", []))
    logs.append("[LangGraph:Node] Executing Validation Agent")

    passed = state.get("validation_passed", False)
    evidence = state.get("validation_evidence", "No evidence recorded")
    inst = (state.get("instructions") or {}).get("validation")

    summary = agent_runner.summarize_validation(
        passed=passed,
        evidence=evidence,
        instructions=inst,
        model=state.get("model"),
    )

    return {
        "validation_summary": summary,
        "status": "VALIDATED",
        "logs": logs,
    }


# -----------------------------------------------------------------------------
# LangGraph Conditional Routers
# -----------------------------------------------------------------------------

def route_after_decision(state: LoopState) -> str:
    """
    LangGraph conditional edge router:
    If validation passed -> route to human_gate or END.
    If validation failed -> check retry budget (attempt < max_attempts):
        - True -> planning_agent (retry loop)
        - False -> stop_node (exhausted attempts)
    """
    if state.get("validation_passed"):
        return "success"

    attempt = state.get("attempt", 1)
    max_attempts = state.get("max_attempts", 3)

    if attempt < max_attempts:
        return "retry_planning"
    return "exhausted_stop"


# -----------------------------------------------------------------------------
# Build & Compile LangGraph Graph
# -----------------------------------------------------------------------------

def build_loop_graph() -> StateGraph:
    """Build the LangGraph StateGraph representing the 4-agent workflow."""
    builder = StateGraph(LoopState)

    # Add Nodes
    builder.add_node("success_criteria", node_success_criteria)
    builder.add_node("planning", node_planning)
    builder.add_node("execution", node_execution)
    builder.add_node("validation", node_validation)

    # Add Edges
    builder.add_edge(START, "success_criteria")
    builder.add_edge("success_criteria", "planning")
    builder.add_edge("planning", "execution")
    builder.add_edge("execution", "validation")

    # Add Conditional Edges from validation
    builder.add_conditional_edges(
        "validation",
        route_after_decision,
        {
            "success": END,
            "retry_planning": "planning",
            "exhausted_stop": END,
        },
    )

    return builder


# Global compiled LangGraph workflow instance
compiled_loop_graph = build_loop_graph().compile()
