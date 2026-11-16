"""Checkpoint regression tests; no game build, API key, or network is required."""

import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from enum import Enum
from pathlib import Path
from unittest.mock import Mock, patch


class Action(Enum):
    NOP = 0
    MOVE_NORTH = 1
    MOVE_SOUTH = 2


class FakeGame:
    def __init__(self, wasm, seed, config):
        self.seed = seed

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def tick(self, action):
        return 1.0


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.config = self.directory / "config.json"
        self.config.write_text(
            '{"completion":{"model":"test-model"}}', encoding="utf-8"
        )
        self.instructions = self.directory / "instructions.md"
        self.instructions.write_text("Test instructions.", encoding="utf-8")

        # Load the runner with a fake game binding so these tests stay independent
        # of NumPy, Wasmtime, and the compiled game.
        game_binding = types.ModuleType("xdgame")
        game_binding.Action = Action
        game_binding.Game = FakeGame
        game_binding.default_config = lambda *args, **kwargs: {}
        spec = importlib.util.spec_from_file_location(
            "checkpoint_test_play", Path(__file__).with_name("play.py")
        )
        self.play = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"xdgame": game_binding}):
            spec.loader.exec_module(self.play)

    @contextmanager
    def run_agent(
        self, log_name, seed=42, action="NOP", memory="Saved memory.", on_request=None
    ):
        def reply(config, messages):
            request_type = json.loads(messages[-1]["content"])["request"]
            if on_request is not None:
                on_request(request_type)
            content = (
                {"action": action}
                if request_type == "action"
                else {"memory": memory}
            )
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(content),
                        },
                    }
                ],
                "usage": {"completion_tokens": 1},
            }

        arguments = [
            "play.py",
            "--config", str(self.config),
            "--instructions", str(self.instructions),
            "--wasm", str(self.directory / "unused.wasm"),
            "--steps", "1",
            "--in-context-steps", "1",
            "--seed", str(seed),
            "--log", str(self.directory / log_name),
        ]
        ask = Mock(side_effect=reply)
        with (
            patch.object(sys, "argv", arguments),
            patch.object(self.play, "ask", ask),
            patch.object(
                self.play, "observation",
                side_effect=lambda game, reward: {"reward": reward},
            ),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            yield ask

    def test_distinct_log_names_keep_both_checkpoints(self):
        runs = [
            ("run.log.jsonl", 11, "MOVE_NORTH", "First run memory."),
            ("run.jsonl", 22, "MOVE_SOUTH", "Second run memory."),
        ]
        for log_name, seed, action, memory in runs:
            with self.run_agent(log_name, seed, action, memory):
                self.play.main()

        for log_name, seed, action, memory in runs:
            with self.subTest(log_name=log_name):
                checkpoint = self.directory / (log_name + ".checkpoint.json")
                self.assertEqual(
                    json.loads(checkpoint.read_text(encoding="utf-8")),
                    {"seed": seed, "actions": [action], "memory": memory},
                )

    def test_existing_checkpoint_is_preserved_before_model_calls(self):
        checkpoint = self.directory / "run.log.jsonl.checkpoint.json"
        original = b'{"seed":7,"actions":["NOP"],"memory":"Keep this."}\n'
        checkpoint.write_bytes(original)

        with self.run_agent("run.log.jsonl") as ask:
            with self.assertRaises(SystemExit) as raised:
                self.play.main()
            self.assertEqual(raised.exception.code, 2)
            ask.assert_not_called()

        self.assertEqual(checkpoint.read_bytes(), original)
        self.assertFalse((self.directory / "run.log.jsonl").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are not available")
    def test_dangling_checkpoint_symlink_is_refused_before_model_calls(self):
        checkpoint = self.directory / "run.log.jsonl.checkpoint.json"
        target = self.directory / "missing.json"
        try:
            checkpoint.symlink_to(target)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Cannot create a symbolic link: {error}")

        with self.run_agent("run.log.jsonl") as ask:
            with self.assertRaises(SystemExit) as raised:
                self.play.main()
            self.assertEqual(raised.exception.code, 2)
            ask.assert_not_called()

        self.assertTrue(checkpoint.is_symlink())
        self.assertEqual(checkpoint.readlink(), target)
        self.assertFalse(target.exists())
        self.assertFalse((self.directory / "run.log.jsonl").exists())

    def test_checkpoint_created_during_run_is_preserved(self):
        checkpoint = self.directory / "run.log.jsonl.checkpoint.json"
        original = b'{"memory":"Another process saved this."}\n'

        def create_checkpoint(request_type):
            if request_type == "action":
                checkpoint.write_bytes(original)

        with self.run_agent("run.log.jsonl", on_request=create_checkpoint) as ask:
            with self.assertRaises(FileExistsError):
                self.play.main()
            self.assertEqual(ask.call_count, 2)

        self.assertEqual(checkpoint.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
