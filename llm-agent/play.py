"""Play 10d-game through an OpenAI-compatible HTTP endpoint."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

import xdgame

ROOT = Path(__file__).resolve().parent
MAX_ATTEMPTS = 10


def observation(game, reward):
    fov = game.fov
    height, width, _ = fov.shape

    return {
        "reward": reward,
        "satiety_level": game.satiety_level,
        "hydration_level": game.hydration_level,
        "inventory_count": game.inventory_count,
        "fov": {
            "beans": [
                [x - width // 2, y - height // 2, int(red), int(green)]
                for y, row in enumerate(fov)
                for x, (red, green, _) in enumerate(row)
                if red or green
            ],
            "channel_3": fov[:, :, 2].tolist(),
        },
    }


def record(log, event, step, **data):
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        "step": step,
        **data,
    }

    log.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    log.flush()


def banner(title, details):
    print(
        f"\n{'=' * 80}\n"
        f"{datetime.now(UTC):%Y-%m-%d %H:%M:%S UTC} | {title}\n"
        f"{details}\n"
        f"{'=' * 80}\n",
        flush=True,
    )


def parse_reply(response):
    choice, *_ = response["choices"]
    if choice["finish_reason"] != "stop":
        raise RuntimeError(f"Model did not finish normally: {choice['finish_reason']}")

    reply = json.loads(choice["message"]["content"])
    if not isinstance(reply, dict) or set(reply) != {"action", "memory"}:
        raise ValueError("Reply must contain exactly action and memory.")
    if (
        not isinstance(reply["action"], str)
        or reply["action"] not in xdgame.Action.__members__
    ):
        raise ValueError(f"Invalid action: {reply['action']!r}")

    memory = reply["memory"]
    if not isinstance(memory, str) or not memory:
        raise ValueError("Memory must be a nonempty string.")

    return xdgame.Action[reply["action"]], memory


def ask(config, messages):
    api_key = (
        os.environ[config["api_key_env"]]
        if config.get("api_key_env")
        else config["api_key"]
    )

    request = Request(
        config["api_base"].rstrip("/") + "/chat/completions",
        data=json.dumps({**config["completion"], "messages": messages}).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(request, timeout=config["timeout"]) as response:
        return json.load(response)


def choose_action(config, messages, log, step, steps):
    output_tokens = 0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempt_label = f"attempt={attempt}/{MAX_ATTEMPTS}"
        position = f"step={step}/{steps} | {attempt_label}"
        record(log, "request", step, attempt=attempt, messages=messages)

        banner(f"MODEL REQUEST | {position}", "Waiting for model...")

        started = perf_counter()
        response = ask(config, messages)
        record(
            log,
            "response",
            step,
            attempt=attempt,
            duration_seconds=perf_counter() - started,
            response=response,
        )

        message = response["choices"][0]["message"]
        reasoning = message.get("reasoning_content") or message.get("reasoning")
        tokens = (response.get("usage") or {}).get("completion_tokens")
        if tokens is None:
            output_tokens = None
        elif output_tokens is not None:
            output_tokens += tokens

        if reasoning:
            print(f"\n[MODEL REASONING]\n{reasoning}", flush=True)

        print(f"\n[MODEL RESPONSE]\n{message.get('content')}", flush=True)

        try:
            action, memory = parse_reply(response)
            output_summary = (
                f"output_tokens={output_tokens}"
                if output_tokens is not None
                else "output_tokens=n/a"
            )
            return action, memory, output_summary
        except (ValueError, TypeError, RuntimeError) as error:
            record(log, "invalid_reply", step, attempt=attempt, error=str(error))

            banner(f"INVALID REPLY | {position}", str(error))

            if attempt == MAX_ATTEMPTS:
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument(
        "--instructions", type=Path, default=ROOT / "agent-instructions.md"
    )
    parser.add_argument(
        "--wasm", type=Path, default=ROOT.parent / "build/10d_game.wasm"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="load seed, action history, and memory from JSON",
    )
    parser.add_argument(
        "--steps",
        type=int,
        required=True,
        help="maximum total game steps, including replayed actions",
    )
    parser.add_argument(
        "--log", type=Path, help="new JSONL file (default: logs/run-*.jsonl)"
    )

    args = parser.parse_args()
    if args.steps < 1:
        parser.error("--steps must be positive")

    config = json.loads(args.config.read_text())
    instructions = args.instructions.read_text()
    actions = []
    memory = ""
    if args.checkpoint:
        checkpoint = json.loads(args.checkpoint.read_text())
        args.seed = checkpoint["seed"]
        actions = checkpoint["actions"]
        memory = checkpoint["memory"]

    completed = len(actions)
    if args.steps <= completed:
        parser.error(f"--steps must exceed the {completed} recorded actions")

    log_path = args.log
    if log_path is None:
        stem = f"run-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-seed_{args.seed}"
        log_path = ROOT / "logs" / f"{stem}.jsonl"
        number = 2
        while log_path.exists():
            log_path = log_path.with_name(f"{stem}-{number}.jsonl")
            number += 1

    log_path.parent.mkdir(parents=True, exist_ok=True)
    reward = None

    with log_path.open("x") as log, xdgame.Game(args.wasm, seed=args.seed) as game:
        for name in actions:
            reward = game.tick(xdgame.Action[name])
        state = observation(game, reward)
        record(
            log,
            "start",
            completed,
            seed=args.seed,
            steps=args.steps,
            settings=config["completion"],
            max_attempts=MAX_ATTEMPTS,
        )
        status = "RUN RESUME" if actions else "RUN START"
        banner(
            f"{status} | seed={args.seed} | step={completed}/{args.steps}",
            f"Log: {log_path}",
        )

        for step in range(completed + 1, args.steps + 1):
            messages = [
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "step": step,
                            "previous_action": actions[-1] if actions else None,
                            "memory": memory,
                            "observation": state,
                        },
                        separators=(",", ":"),
                    ),
                },
            ]

            turn_started = perf_counter()
            action, next_memory, output_summary = choose_action(
                config, messages, log, step, args.steps
            )
            duration = perf_counter() - turn_started

            reward = game.tick(action)
            state = observation(game, reward)
            memory = next_memory
            actions.append(action.name)

            record(log, "transition", step, action=action.name, observation=state)
            banner(
                f"STEP COMPLETE | step={step}/{args.steps}",
                f"action={action.name} {output_summary} duration={duration:.2f}s",
            )

        checkpoint_path = ROOT / "checkpoint.json"
        checkpoint_path.write_text(
            json.dumps(
                {"seed": args.seed, "actions": actions, "memory": memory},
                ensure_ascii=False,
            )
            + "\n"
        )
        record(log, "end", args.steps, memory=memory)
        banner(
            f"RUN COMPLETE | step={args.steps}/{args.steps}",
            f"Log: {log_path}\nCheckpoint: {checkpoint_path}",
        )


if __name__ == "__main__":
    main()
