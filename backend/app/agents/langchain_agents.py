from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.agents import tools as repo_tools
from app.agents.llm import resolve_provider, use_mock
from app.models import FileChange


def get_langchain_chat_model(
    model_name: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """
    Factory function returning a LangChain ChatOpenAI instance configured for the
    requested model and provider (OpenAI, Gemini, Mistral, etc.).
    """
    provider, model_id = resolve_provider(model_name)

    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        base_url = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        model_kwargs = {}
        if json_mode:
            model_kwargs["response_format"] = {"type": "json_object"}
        return ChatOpenAI(
            model=model_id,
            api_key=key,
            base_url=base_url,
            temperature=temperature,
            model_kwargs=model_kwargs,
        )

    if provider == "mistral":
        key = os.getenv("MISTRAL_API_KEY")
        if not key:
            raise RuntimeError("MISTRAL_API_KEY is not set")
        base_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
        model_kwargs = {}
        if json_mode:
            model_kwargs["response_format"] = {"type": "json_object"}
        return ChatOpenAI(
            model=model_id,
            api_key=key,
            base_url=base_url,
            temperature=temperature,
            model_kwargs=model_kwargs,
        )

    # Default to OpenAI
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base_url = os.getenv("OPENAI_BASE_URL") or None
    model_kwargs = {}
    if json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}
    return ChatOpenAI(
        model=model_id,
        api_key=key,
        base_url=base_url,
        temperature=temperature,
        model_kwargs=model_kwargs,
    )


# -----------------------------------------------------------------------------
# LangChain Prompt Templates
# -----------------------------------------------------------------------------

SUCCESS_CRITERIA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_instructions}\n\n"
               "CRITICAL RULES:\n"
               "1. Derive success criteria STRICTLY from the user's Objective and Constraints.\n"
               "2. DO NOT introduce or assume specific filenames (such as 'src/app.js') unless explicitly specified by the user in the prompt or scope context.\n"
               "3. You MUST respond with a valid JSON object containing a single key 'criteria' "
               "which is an array of strings representing measurable, verifiable completion criteria."),
    ("user", "Objective:\n{objective}\n\n"
             "Constraints:\n{constraints}\n\n"
             "Scope Context:\n{scope_note}")
])

PLANNING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_instructions}\n\n"
               "CRITICAL: You MUST respond with a valid JSON object with keys:\n"
               "- 'steps': array of concrete step strings naming real files\n"
               "- 'plan': markdown string describing the architectural plan, sequence of work, and risk analysis."),
    ("user", "Objective:\n{objective}\n\n"
             "Constraints:\n{constraints}\n\n"
             "Success Criteria:\n{criteria_json}\n\n"
             "Previous Failure Feedback (if any):\n{feedback}\n\n"
             "Repository Structure:\n{repo_listing}\n\n"
             "Sample File ({sample_path}):\n{sample_src}\n\n"
             "Scope Notes:\n{scope_note}")
])

EXECUTION_SYSTEM_PROMPT = (
    "{system_instructions}\n\n"
    "Scope context:\n{scope_note}\n\n"
    "Available tools: list_dir, read_file, write_file, search, grep_search, run_shell.\n"
    "Use grep_search to find exact function names, routes, or code patterns across the repository.\n"
    "Use your tools to inspect and modify the repository. Stop when the task is complete."
)

VALIDATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{system_instructions}\n\n"
               "Deterministic Verdict is fixed as: {verdict_str}. Do not alter the verdict."),
    ("user", "Validation Evidence:\n{evidence}")
])


# -----------------------------------------------------------------------------
# LangChain Agent Execution Functions
# -----------------------------------------------------------------------------

def run_langchain_success_criteria(
    *,
    objective: str,
    constraints: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    scope_note: str = "",
) -> dict[str, Any]:
    """Execute Success Criteria Agent using LangChain ChatPromptTemplate + ChatModel."""
    chat_model = get_langchain_chat_model(model_name=model, json_mode=True)
    chain = SUCCESS_CRITERIA_PROMPT | chat_model

    default_system = (
        "You are the Success Criteria Agent for LoopForge AI Coding Platform. "
        "Convert the engineering objective into specific, measurable, verifiable completion criteria."
    )
    sys_inst = instructions or default_system

    response = chain.invoke({
        "system_instructions": sys_inst,
        "objective": objective,
        "constraints": constraints,
        "scope_note": scope_note,
    })

    content = response.content if isinstance(response.content, str) else str(response.content)
    try:
        parsed = json.loads(content)
        criteria = parsed.get("criteria") or []
    except Exception:
        criteria = [content]

    raw = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria))
    return {"criteria": criteria, "raw": raw}


def _get_qdrant_rag_context(query: str, limit: int = 4) -> str:
    """Retrieve relevant code chunks combining Qdrant vector database and grep pattern search."""
    context_blocks = []
    try:
        from app.rag.indexer import rag_manager
        status = rag_manager.get_status()
        if status.get("indexed"):
            results = rag_manager.search(query=query, limit=limit)
            if results:
                blocks = []
                for r in results:
                    blocks.append(
                        f"--- File: {r['path']} (Qdrant Match Score: {r['score']}) ---\n{r['content']}"
                    )
                context_blocks.append("[Qdrant Semantic Vector Context]:\n" + "\n\n".join(blocks))
    except Exception:
        pass

    try:
        from app.agents import tools as repo_tools
        keywords = [w for w in query.split() if len(w) > 3 and w.isalnum()]
        if keywords:
            search_term = keywords[0]
            grep_res = repo_tools.grep_search(query=search_term, rel_path=".")
            if grep_res:
                grep_lines = []
                for g in grep_res[:8]:
                    if "file" in g and "content" in g:
                        grep_lines.append(f"  {g['file']}:{g['line']} -> {g['content']}")
                if grep_lines:
                    context_blocks.append(f"[Grep Pattern Search Context for '{search_term}']:\n" + "\n".join(grep_lines))
    except Exception:
        pass

    return ("\n\n" + "\n\n".join(context_blocks)) if context_blocks else ""



def run_langchain_planning(
    *,
    objective: str,
    constraints: str,
    criteria: list[str],
    feedback: Optional[str] = None,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    repo_listing: str = "",
    sample_path: str = "src/app.js",
    sample_src: str = "",
    scope_note: str = "",
) -> dict[str, Any]:
    """Execute Planning Agent using LangChain ChatPromptTemplate + ChatModel."""
    chat_model = get_langchain_chat_model(model_name=model, json_mode=True)
    chain = PLANNING_PROMPT | chat_model

    default_system = (
        "You are the Planning Agent for LoopForge AI Coding Platform. "
        "Create a concrete, step-by-step implementation plan grounded in real files in the repository."
    )
    sys_inst = instructions or default_system
    rag_context = _get_qdrant_rag_context(query=objective)
    combined_scope = (scope_note or "") + rag_context

    response = chain.invoke({
        "system_instructions": sys_inst,
        "objective": objective,
        "constraints": constraints,
        "criteria_json": json.dumps(criteria),
        "feedback": feedback or "None",
        "repo_listing": repo_listing,
        "sample_path": sample_path,
        "sample_src": sample_src,
        "scope_note": combined_scope,
    })


    content = response.content if isinstance(response.content, str) else str(response.content)
    try:
        parsed = json.loads(content)
        steps = parsed.get("steps") or []
        plan = parsed.get("plan") or "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
    except Exception:
        plan = content
        steps = [content]

    return {"plan": plan, "steps": steps, "raw": plan}


def run_langchain_execution(
    *,
    objective: str,
    plan: str,
    criteria: list[str],
    feedback: Optional[str] = None,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    execute_tool_func: Callable[[str, dict[str, Any]], str],
    tools_defs: list[dict[str, Any]],
    scope_note: str = "",
    max_rounds: int = 8,
) -> dict[str, Any]:
    """
    Execute Execution Agent using LangChain ChatModel with tool calling.
    """
    chat_model = get_langchain_chat_model(model_name=model, json_mode=False)

    # Bind OpenAI tools to the LangChain model
    model_with_tools = chat_model.bind(tools=tools_defs)

    sys_inst = instructions or "Implement the planned changes in the codebase using tools."
    system_text = EXECUTION_SYSTEM_PROMPT.format(
        system_instructions=sys_inst,
        scope_note=scope_note,
    )

    user_text = json.dumps({
        "objective": objective,
        "plan": plan,
        "criteria": criteria,
        "feedback": feedback or "",
    })

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=user_text),
    ]

    transcript: list[str] = []
    files_changed: list[FileChange] = []

    for _ in range(max_rounds):
        ai_msg = model_with_tools.invoke(messages)
        messages.append(ai_msg)

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            msg_str = ai_msg.content if isinstance(ai_msg.content, str) else str(ai_msg.content)
            transcript.append(msg_str or "Execution finished")
            break

        for tool_call in tool_calls:
            name = tool_call["name"]
            args = tool_call["args"]
            tool_call_id = tool_call["id"]

            try:
                result = execute_tool_func(name, args)
            except Exception as exc:
                result = f"Error: {exc}"

            if name == "write_file":
                transcript.append(f"Wrote {args.get('path')}")
            elif name == "run_shell":
                try:
                    parsed = json.loads(result)
                    transcript.append(f"$ {args.get('command')} → exit {parsed.get('exitCode')}")
                except Exception:
                    transcript.append(f"$ {args.get('command')}")

            messages.append(
                ToolMessage(
                    content=str(result)[:8000],
                    tool_call_id=tool_call_id,
                )
            )

    return {
        "summary": transcript[-1] if transcript else "Execution complete",
        "filesChanged": files_changed,
        "transcript": transcript,
    }


def run_langchain_validation(
    *,
    passed: bool,
    evidence: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Execute Validation Agent using LangChain ChatPromptTemplate + ChatModel."""
    chat_model = get_langchain_chat_model(model_name=model, json_mode=False)
    chain = VALIDATION_PROMPT | chat_model

    default_system = (
        "Summarize validation evidence clearly for the user. Never override or alter the pass/fail verdict."
    )
    sys_inst = instructions or default_system

    response = chain.invoke({
        "system_instructions": sys_inst,
        "verdict_str": "PASS" if passed else "FAIL",
        "evidence": evidence,
    })

    return response.content if isinstance(response.content, str) else str(response.content)
