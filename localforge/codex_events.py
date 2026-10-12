"""Extract run metrics from Codex's JSONL event stream."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


_TEST_COMMAND = re.compile(
    r"(?:^|[\s;&|])(?:pytest|python(?:3)?\s+-m\s+(?:pytest|unittest)|"
    r"poetry\s+run\s+(?:pytest|python(?:3)?\s+-m\s+(?:pytest|unittest))|"
    r"npm\s+(?:run\s+)?test|cargo\s+test|go\s+test|dotnet\s+test)(?:\s|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class TestRun:
    command: str
    exit_code: int | None


@dataclass(frozen=True)
class CodexEvents:
    usage: TokenUsage | None
    test_runs: tuple[TestRun, ...]
    final_message: str | None


def parse_codex_events(stdout: str) -> CodexEvents:
    """Read completed turns and test commands, tolerating missing usage."""
    usages: list[TokenUsage] = []
    tests: list[TestRun] = []
    final_message = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
            if not isinstance(usage, dict):
                continue
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if not all(type(value) is int and value >= 0 for value in (input_tokens, output_tokens)):
                continue
            cached = usage.get("cached_input_tokens", 0)
            reasoning = usage.get("reasoning_output_tokens", 0)
            usages.append(TokenUsage(input_tokens, output_tokens,
                                     cached if type(cached) is int else 0,
                                     reasoning if type(reasoning) is int else 0))
        elif event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                message = item.get("text")
                if isinstance(message, str):
                    final_message = message
            if isinstance(item, dict) and item.get("type") == "command_execution":
                command = item.get("command")
                if isinstance(command, str) and _TEST_COMMAND.search(command):
                    exit_code = item.get("exit_code")
                    tests.append(TestRun(command, exit_code if type(exit_code) is int else None))
    total = None
    if usages:
        total = TokenUsage(
            sum(item.input_tokens for item in usages),
            sum(item.output_tokens for item in usages),
            sum(item.cached_input_tokens for item in usages),
            sum(item.reasoning_output_tokens for item in usages),
        )
    return CodexEvents(total, tuple(tests), final_message)
