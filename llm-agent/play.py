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


def parse_reply(response, request_type):
    choice, *_ = response["choices"]

    if choice["finish_reason"] != "stop":
        raise RuntimeError(f"Model did not finish normally: {choice['finish_reason']}")

    reply = json.loads(choice["message"]["content"])
    fields = {"memory"} if request_type == "summary" else {"action"}
    if not isinstance(reply, dict) or set(reply) != fields:
        raise ValueError(f"Reply must contain exactly {', '.join(sorted(fields))}.")

    if request_type == "action" and (
        not isinstance(reply["action"], str)
        or reply["action"] not in xdgame.Action.__members__
    ):
        raise ValueError(f"Invalid action: {reply['action']!r}")

    if request_type == "summary" and (
        not isinstance(reply["memory"], str) or not reply["memory"].strip()
    ):
        raise ValueError("Memory must be a nonempty string.")

    return reply


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


def get_reply(config, messages, log, step, steps):
    output_tokens = 0
    original_messages = messages
    request_type = json.loads(messages[-1]["content"])["request"]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempt_label = f"attempt={attempt}/{MAX_ATTEMPTS}"
        position = f"{request_type.upper()} | step={step}/{steps} | {attempt_label}"

        record(
            log,
            "request",
            step,
            request_type=request_type,
            attempt=attempt,
            messages=messages,
        )

        banner(f"MODEL REQUEST | {position}", "Waiting for model...")

        started = perf_counter()
        response = ask(config, messages)
        record(
            log,
            "response",
            step,
            request_type=request_type,
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
            reply = parse_reply(response, request_type)
            output_summary = (
                f"output_tokens={output_tokens}"
                if output_tokens is not None
                else "output_tokens=n/a"
            )

            original_messages.append(message)
            return reply, output_summary
        except (ValueError, TypeError, RuntimeError) as error:
            record(
                log,
                "invalid_reply",
                step,
                request_type=request_type,
                attempt=attempt,
                error=str(error),
            )

            banner(f"INVALID REPLY | {position}", str(error))

            if attempt == MAX_ATTEMPTS:
                raise

            prompt = json.loads(original_messages[-1]["content"])
            prompt["reply_error"] = str(error)
            if request_type == "action":
                prompt["reply_error"] += (
                    f"\nValid action names: {', '.join(xdgame.Action.__members__)}."
                )

            messages = original_messages[:-1] + [
                {
                    "role": "user",
                    "content": json.dumps(prompt, separators=(",", ":")),
                },
            ]


def summarize(config, messages, state, log, step, steps):
    prompt = {
        "request": "summary",
        "instructions": (
            "This episode's actions are complete. After your summary is accepted, the "
            "next teammate continues the same game from this state without a reset. It "
            "receives only your new memory, the game instructions, and the latest "
            "observation. All other context is lost: anything learned, inferred, or "
            "planned that you omit from memory will not be available to it. Write a "
            "complete, self-explanatory memory that stands on its own, without "
            "references to this conversation or earlier messages. Combine prior memory "
            "with this episode's observations and reasoning, including the last "
            "action's result shown in observation. Follow the memory requirements in "
            "the game instructions. Return only a JSON object with a nonempty memory "
            "string; do not choose an action."
        ),
        "observation": state,
        "reply_error": None,
    }

    messages.append(
        {"role": "user", "content": json.dumps(prompt, separators=(",", ":"))}
    )

    started = perf_counter()
    reply, output_summary = get_reply(config, messages, log, step, steps)
    memory = reply["memory"]

    record(log, "summary", step, memory=memory)
    banner(
        f"SUMMARY COMPLETE | step={step}/{steps}",
        f"{output_summary} duration={perf_counter() - started:.2f}s",
    )

    return memory


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
        help=(
            "total game steps, including replayed actions, "
            "rounded up to --in-context-steps"
        ),
    )
    parser.add_argument(
        "--in-context-steps",
        type=int,
        default=25,
        help="game steps retained in context before summarizing (default: 25)",
    )

    parser.add_argument(
        "--log", type=Path, help="new JSONL file (default: logs/run-*.log.jsonl)"
    )

    args = parser.parse_args()

    if args.steps < 1:
        parser.error("--steps must be positive")
    if args.in_context_steps < 1:
        parser.error("--in-context-steps must be positive")

    args.steps = (
        (args.steps + args.in_context_steps - 1)
        // args.in_context_steps
        * args.in_context_steps
    )

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
        log_path = ROOT / "logs" / f"{stem}.log.jsonl"
        number = 2
        while log_path.exists():
            log_path = log_path.with_name(f"{stem}-{number}.log.jsonl")
            number += 1

    log_path.parent.mkdir(parents=True, exist_ok=True)

    reward = None
    game_config = xdgame.default_config(
        args.wasm, initial_satiety=20, initial_hydration=60
    )

    with (
        log_path.open("x") as log,
        xdgame.Game(args.wasm, seed=args.seed, config=game_config) as game,
    ):
        for name in actions:
            reward = game.tick(xdgame.Action[name])

        state = observation(game, reward)

        record(
            log,
            "start",
            completed,
            seed=args.seed,
            steps=args.steps,
            in_context_steps=args.in_context_steps,
            settings=config["completion"],
            max_attempts=MAX_ATTEMPTS,
        )

        status = "RUN RESUME" if actions else "RUN START"
        banner(
            f"{status} | seed={args.seed} | step={completed}/{args.steps}",
            f"in_context_steps={args.in_context_steps}\nLog: {log_path}",
        )

        messages = [{"role": "system", "content": instructions}]
        episode_start = completed

        for step in range(completed + 1, args.steps + 1):
            prompt = {
                "request": "action",
                "step": step,
                "episode_step": step - episode_start,
                "episode_steps": (
                    args.in_context_steps - episode_start % args.in_context_steps
                ),
                "previous_action": actions[-1] if actions else None,
                "observation": state,
                "reply_error": None,
            }
            if len(messages) == 1:
                prompt["memory"] = memory

            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(prompt, separators=(",", ":")),
                }
            )

            turn_started = perf_counter()
            reply, output_summary = get_reply(config, messages, log, step, args.steps)
            duration = perf_counter() - turn_started

            action = xdgame.Action[reply["action"]]
            reward = game.tick(action)
            state = observation(game, reward)
            actions.append(action.name)

            record(log, "transition", step, action=action.name, observation=state)
            banner(
                f"STEP COMPLETE | step={step}/{args.steps}",
                f"action={action.name} {output_summary} duration={duration:.2f}s",
            )

            if step % args.in_context_steps == 0:
                memory = summarize(config, messages, state, log, step, args.steps)
                messages = [{"role": "system", "content": instructions}]
                episode_start = step

        checkpoint_path = log_path.with_name(
            log_path.stem.removesuffix(".log") + ".checkpoint.json"
        )

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
