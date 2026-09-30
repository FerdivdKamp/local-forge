"""Tests for metrics extracted from Codex JSONL output."""

from __future__ import annotations

import json
import unittest

from localforge.codex_events import parse_codex_events


class CodexEventTests(unittest.TestCase):
    def test_sums_completed_turns_and_records_test_results(self) -> None:
        events = [
            {"type": "item.completed", "item": {"type": "command_execution",
                                           "command": "poetry run python -m unittest discover -s tests",
                                           "exit_code": 0}},
            {"type": "item.completed", "item": {"type": "command_execution",
                                           "command": "git status --short", "exit_code": 0}},
            {"type": "turn.completed", "usage": {"input_tokens": 100,
                                                  "cached_input_tokens": 20,
                                                  "output_tokens": 30,
                                                  "reasoning_output_tokens": 5}},
            {"type": "turn.completed", "usage": {"input_tokens": 40,
                                                  "output_tokens": 10}},
            {"type": "item.completed", "item": {"type": "agent_message",
                                           "text": "Implemented and tested."}},
        ]
        parsed = parse_codex_events("\n".join(json.dumps(event) for event in events))
        self.assertEqual(parsed.usage.input_tokens, 140)
        self.assertEqual(parsed.usage.output_tokens, 40)
        self.assertEqual(parsed.usage.cached_input_tokens, 20)
        self.assertEqual(parsed.usage.total_tokens, 180)
        self.assertEqual(len(parsed.test_runs), 1)
        self.assertEqual(parsed.test_runs[0].exit_code, 0)
        self.assertEqual(parsed.final_message, "Implemented and tested.")

    def test_missing_or_invalid_usage_is_unknown(self) -> None:
        parsed = parse_codex_events(
            'not json\n{"type":"turn.completed","usage":null}\n'
            '{"type":"turn.completed","usage":{"input_tokens":true,"output_tokens":3}}'
        )
        self.assertIsNone(parsed.usage)
        self.assertEqual(parsed.test_runs, ())
