"""Prompt utilities for agent orchestration."""

from __future__ import annotations

import os
from typing import Dict, List


def build_tool_descriptions(tool_schemas: List[Dict]) -> str:
    lines = []
    for schema in tool_schemas:
        fn = schema["function"]
        params = fn.get("parameters", {}).get("properties", {})
        param_str = ", ".join(
            f'{name} ({meta.get("type", "any")}): {meta.get("description", "")}'
            for name, meta in params.items()
        )
        lines.append(f'- {fn["name"]}: {fn["description"]}\n  Args: {param_str}')
    return "\n".join(lines)


def load_system_prompt(tool_schemas: List[Dict]) -> str:
    """Load prompt template from file and inject tool descriptions."""
    prompt_file = os.path.join(os.path.dirname(__file__), "..", "prompts", "agent_system.txt")
    prompt_file = os.path.normpath(prompt_file)
    try:
        with open(prompt_file, "r", encoding="utf-8") as file:
            template = file.read()
    except FileNotFoundError as exc:
        raise RuntimeError(f"Agent system prompt not found at {prompt_file}") from exc

    return template.replace("{tool_descriptions}", build_tool_descriptions(tool_schemas))


def build_chat_prompt(
    system_prompt: str,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    ticker_hint: str = "",
) -> str:
    """Build chat transcript prompt consumed by the LLM backend."""
    prompt_parts: List[str] = [f"[SYSTEM]\n{system_prompt}\n"]
    for msg in conversation_history[-10:]:
        role = msg.get("role", "user").capitalize()
        prompt_parts.append(f"[{role}]\n{msg.get('content', '')}\n")

    user_block = f"[User]\n{user_message}\n[Assistant]"
    if ticker_hint:
        user_block = f"[User]\n{user_message}\n{ticker_hint}\n[Assistant]"

    prompt_parts.append(user_block)
    return "\n".join(prompt_parts)
