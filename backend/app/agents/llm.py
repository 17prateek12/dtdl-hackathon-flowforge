from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

# Ensure .env is loaded before reading any env vars (paths.py calls load_dotenv)
import app.paths  # noqa: F401


@dataclass
class ModelOption:
    id: str
    label: str
    provider: str
    available: bool
    env_key: str


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def _mistral_model_id() -> str:
    return (
        os.getenv("MISTRAL_MODEL")
        or os.getenv("CHAT_MODEL")
        or "mistral-small-latest"
    )


def list_models() -> list[ModelOption]:
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    mistral_model = _mistral_model_id()

    return [
        ModelOption(
            id=mistral_model,
            label=f"Mistral · {mistral_model}",
            provider="mistral",
            available=bool(os.getenv("MISTRAL_API_KEY")),
            env_key="MISTRAL_API_KEY",
        ),
        ModelOption(
            id=openai_model,
            label=f"OpenAI · {openai_model}",
            provider="openai",
            available=bool(os.getenv("OPENAI_API_KEY")),
            env_key="OPENAI_API_KEY",
        ),
        ModelOption(
            id=anthropic_model,
            label=f"Anthropic · {anthropic_model}",
            provider="anthropic",
            available=bool(os.getenv("ANTHROPIC_API_KEY")),
            env_key="ANTHROPIC_API_KEY",
        ),
        ModelOption(
            id=gemini_model,
            label=f"Gemini · {gemini_model}",
            provider="gemini",
            available=bool(os.getenv("GEMINI_API_KEY")),
            env_key="GEMINI_API_KEY",
        ),
    ]


def any_provider_configured() -> bool:
    return any(m.available for m in list_models())


def use_mock() -> bool:
    # Default is FALSE — real LLM is used unless MOCK_AGENTS=true is explicitly set
    if _truthy("MOCK_AGENTS", "false"):
        return True
    return not any_provider_configured()


def resolve_provider(model: Optional[str]) -> tuple[str, str]:
    """Return (provider, model_id) for a requested model string."""
    models = list_models()
    by_id = {m.id: m for m in models}
    if model and model in by_id:
        return by_id[model].provider, by_id[model].id

    lowered = (model or "").lower()
    if lowered.startswith("mistral") or "mistral" in lowered:
        m = next(x for x in models if x.provider == "mistral")
        return "mistral", model or m.id
    if lowered.startswith("claude") or "anthropic" in lowered:
        m = next(x for x in models if x.provider == "anthropic")
        return "anthropic", model or m.id
    if lowered.startswith("gemini") or "google" in lowered:
        m = next(x for x in models if x.provider == "gemini")
        return "gemini", model or m.id

    # Prefer Mistral when configured, else OpenAI
    if os.getenv("MISTRAL_API_KEY"):
        m = next(x for x in models if x.provider == "mistral")
        return "mistral", model or m.id
    m = next(x for x in models if x.provider == "openai")
    return "openai", model or m.id


def _openai_client(provider: str):
    from openai import OpenAI

    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        base = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        return OpenAI(api_key=key, base_url=base)

    if provider == "mistral":
        key = os.getenv("MISTRAL_API_KEY")
        if not key:
            raise RuntimeError("MISTRAL_API_KEY is not set")
        base = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
        return OpenAI(api_key=key, base_url=base)

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base = os.getenv("OPENAI_BASE_URL") or None
    return OpenAI(api_key=key, base_url=base)


def chat_text(
    *,
    model: Optional[str],
    system: str,
    user: str,
    json_mode: bool = False,
) -> str:
    provider, model_id = resolve_provider(model)

    if provider == "anthropic":
        return _anthropic_text(
            model_id=model_id, system=system, user=user, json_mode=json_mode
        )

    if json_mode:
        has_json = "json" in (system or "").lower() or "json" in (user or "").lower()
        if not has_json:
            system = (system or "") + "\n\nNote: You must respond in valid JSON format."

    client = _openai_client(provider)
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode and provider in {"openai", "mistral", "gemini"}:
        kwargs["response_format"] = {"type": "json_object"}
    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content or ""


def _anthropic_text(
    *, model_id: str, system: str, user: str, json_mode: bool
) -> str:
    from anthropic import Anthropic

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = Anthropic(api_key=key)
    prompt = user
    if json_mode:
        prompt = user + "\n\nRespond with valid JSON only."
    msg = client.messages.create(
        model=model_id,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts)


def chat_with_tools(
    *,
    model: Optional[str],
    system: str,
    user: str,
    tools: list[dict[str, Any]],
    execute_tool,
    max_rounds: int = 8,
) -> tuple[list[str], list[Any]]:
    """
    Tool-calling loop. execute_tool(name, args) -> str
    Returns (transcript, files_changed_accumulator_unused — caller manages files).
    """
    provider, model_id = resolve_provider(model)
    transcript: list[str] = []

    if provider == "anthropic":
        return _anthropic_tools(
            model_id=model_id,
            system=system,
            user=user,
            tools=tools,
            execute_tool=execute_tool,
            transcript=transcript,
            max_rounds=max_rounds,
        )

    client = _openai_client(provider)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    for _ in range(max_rounds):
        completion = client.chat.completions.create(
            model=model_id,
            messages=messages,
            tools=tools,
        )
        msg = completion.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            transcript.append(msg.content or "Execution finished")
            break
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            try:
                result = execute_tool(call.function.name, args)
            except Exception as exc:  # noqa: BLE001
                result = f"Error: {exc}"
            if call.function.name == "write_file":
                transcript.append(f"Wrote {args.get('path')}")
            if call.function.name == "run_shell":
                try:
                    parsed = json.loads(result)
                    transcript.append(
                        f"$ {args.get('command')} → exit {parsed.get('exitCode')}"
                    )
                except Exception:  # noqa: BLE001
                    transcript.append(f"$ {args.get('command')}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result)[:8000],
                }
            )

    return transcript, []


def _anthropic_tools(
    *,
    model_id: str,
    system: str,
    user: str,
    tools: list[dict[str, Any]],
    execute_tool,
    transcript: list[str],
    max_rounds: int,
) -> tuple[list[str], list[Any]]:
    from anthropic import Anthropic

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = Anthropic(api_key=key)

    anthropic_tools = []
    for t in tools:
        fn = t.get("function") or {}
        anthropic_tools.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description") or "",
                "input_schema": fn.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )

    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]

    for _ in range(max_rounds):
        msg = client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=system,
            tools=anthropic_tools,
            messages=messages,
        )
        assistant_content = msg.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_uses = [b for b in assistant_content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            texts = [
                b.text for b in assistant_content if getattr(b, "type", None) == "text"
            ]
            transcript.append("\n".join(texts) or "Execution finished")
            break

        tool_results = []
        for block in tool_uses:
            name = block.name
            args = block.input if isinstance(block.input, dict) else {}
            try:
                result = execute_tool(name, args)
            except Exception as exc:  # noqa: BLE001
                result = f"Error: {exc}"
            if name == "write_file":
                transcript.append(f"Wrote {args.get('path')}")
            if name == "run_shell":
                transcript.append(f"$ {args.get('command')}")
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result)[:8000],
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return transcript, []


def _mock_embedding(text: str, dimensions: int = 1536) -> list[float]:
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vector = []
    for i in range(dimensions):
        byte_index = (i * 3) % len(h)
        val = (h[byte_index] - 128.0) / 128.0
        vector.append(val)
    norm = sum(x*x for x in vector) ** 0.5
    return [x / norm for x in vector] if norm > 0 else [0.0] * dimensions


def get_embedding(text: str, model: Optional[str] = None) -> list[float]:
    if use_mock():
        return _mock_embedding(text)
        
    provider, _ = resolve_provider(model)
    
    if provider == "openai" or os.getenv("OPENAI_API_KEY"):
        try:
            client = _openai_client("openai")
            resp = client.embeddings.create(
                input=[text],
                model="text-embedding-3-small"
            )
            return resp.data[0].embedding
        except Exception:
            pass
            
    if provider == "gemini" or os.getenv("GEMINI_API_KEY"):
        try:
            client = _openai_client("gemini")
            resp = client.embeddings.create(
                input=[text],
                model="text-embedding-004"
            )
            return resp.data[0].embedding
        except Exception:
            pass
            
    return _mock_embedding(text)
