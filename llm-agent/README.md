# 10d-game LLM agent

This directory provides a headless runner for language-model agents in
10d-game. The agent learns game mechanics through observations and rewards.

[play.py] uses the [Python bindings] to run the game and sends requests directly
to an OpenAI-compatible model server. Each reply supplies one action and memory
for the next request. Tools are not available to the agent.

[agent-instructions.md] defines the objective, observations, actions, and
response format. Edit it to change the instructions supplied to the model.

## Setup

The runner requires [uv], Python 3.14 or newer, and a compiled
[WebAssembly module]. Follow the [Python bindings] instructions to obtain the
engine. Its default location is `build/10d_game.wasm` in the repository root;
use `--wasm` to select another file.

From the repository root, create your local model configuration:

```bash
cp llm-agent/config.json.EXAMPLE llm-agent/config.json
```

Edit `api_base` and the `completion` settings for your model server. Include
`/v1` in `api_base` if required. Generation parameters are sent unchanged; the
example's Qwen/vLLM settings may need adjustment for other models.

The server must accept non-streaming Chat Completions requests with Bearer
authentication and text system/user messages, and return the standard response
with `finish_reason: "stop"`. The model must follow the JSON action/memory
format in [agent-instructions.md].

Supply the API key through the environment variable named by `api_key_env`:

```bash
export MODEL_API_KEY='your-api-key'
```

`config.json` is ignored by Git; only [config.json.EXAMPLE] should be committed.

## Run

From the repository root, use the Python binding's [uv] environment:

```bash
uv run --project bindings/python llm-agent/play.py --seed 42 --steps 10
```

`--steps` is required. Reasoning and answers are printed after each response
completes. Progress banners include step counts, durations, and output tokens
across all attempts, or `n/a` when usage is unavailable. Add `--help` for all
options, including alternate config and instruction files.

## Continue a run

After successful completion, `llm-agent/checkpoint.json` is overwritten with
three fields: `seed`, `actions`, and `memory`. To continue to twenty steps:

```bash
uv run --project bindings/python llm-agent/play.py \
    --checkpoint llm-agent/checkpoint.json --steps 20
```

After a ten-step run, this performs ten new actions. The saved seed is used, and
previous actions are replayed without model calls. Use the same engine and game
configuration. Without `--checkpoint`, a new game starts. Interrupted or failed
runs do not update the checkpoint.

## Recorded output

Full JSONL logs are saved under `llm-agent/logs/`. Use `--log` to select another
file. Console output goes to stdout; unhandled exceptions go to stderr. To
display and save the readable output:

```bash
uv run --project bindings/python llm-agent/play.py --seed 42 --steps 100 \
    | tee -i llm-agent/progress.txt
```

Invalid replies get up to ten attempts per step without advancing the game.
The tenth failure stops the program. API and transport errors stop immediately.
Logs, checkpoints, and `progress.txt` are ignored by Git.

[uv]: https://docs.astral.sh/uv/
[Python bindings]: ../bindings/python/README.md
[WebAssembly module]: ../bindings/python/README.md#install-from-source
[config.json.EXAMPLE]: config.json.EXAMPLE
[play.py]: play.py
[agent-instructions.md]: agent-instructions.md
