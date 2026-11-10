# 10d-game LLM agent

This directory provides a headless runner for language-model agents in
10d-game. The agent learns game mechanics through observations and rewards.

[play.py] uses the [Python bindings] to run the game and sends requests directly
to an OpenAI-compatible model server. Each action reply supplies one action.
After each block of steps, a separate request summarizes the conversation into
memory for the next block. Tools are not available to the agent.

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
authentication and text system/user/assistant messages, and return the standard
response with `finish_reason: "stop"`. The model must follow the JSON response
formats in [agent-instructions.md]. For reasoning models, the server must accept
and retain reasoning fields in historical assistant messages. The example
enables Qwen's `preserve_thinking` setting.

Supply the API key through the environment variable named by `api_key_env`:

```bash
export MODEL_API_KEY='your-api-key'
```

`config.json` is ignored by Git; only [config.json.EXAMPLE] should be committed.

## Run

From the repository root, use the Python binding's [uv] environment:

```bash
uv run --project bindings/python llm-agent/play.py --seed 42 --steps 25
```

`--steps` is required and rounded up to a multiple of `--in-context-steps`
(default: 25). For example, `--steps 30 --in-context-steps 25` runs 50 actions.
Each block retains its observations and complete accepted replies, including
reasoning, then makes one extra summary call without advancing the game. Only
that summary carries into the next block. Reasoning counts toward the context
window; choose `--in-context-steps` to leave room for memory and the next reply.

Reasoning and answers are printed after each response completes. Progress
banners distinguish actions and summaries, with step counts, durations, and
output tokens across all attempts, or `n/a` when usage is unavailable. Add
`--help` for all options, including alternate config and instruction files.

## Continue a run

After successful completion, a checkpoint is saved beside the log with the
same run name. Default logs use `.log.jsonl`; checkpoints use
`.checkpoint.json`. For example,
`logs/run-20261101T120000Z-seed_42.log.jsonl` is paired with
`logs/run-20261101T120000Z-seed_42.checkpoint.json`. The checkpoint contains
three fields: `seed`, `actions`, and `memory`. Use the checkpoint path printed
at completion to continue from 25 to 50 steps:

```bash
uv run --project bindings/python llm-agent/play.py \
    --checkpoint llm-agent/logs/run-20261101T120000Z-seed_42.checkpoint.json \
    --steps 50
```

After a run of 25 steps, this performs 25 new actions. The saved seed is used,
and previous actions are replayed without model calls. Use the same engine and
game configuration. If a checkpoint ends between block boundaries, the first
block ends at the next multiple of `--in-context-steps`. Without `--checkpoint`,
a new game starts. Interrupted or failed runs do not write a new checkpoint.

## Recorded output

Full JSONL logs are saved under `llm-agent/logs/`. Use `--log` to select another
file. Console output goes to stdout; unhandled exceptions go to stderr. To
display and save the readable output:

```bash
uv run --project bindings/python llm-agent/play.py --seed 42 --steps 100 \
    | tee -i llm-agent/progress.txt
```

Invalid replies get up to ten attempts per action or summary without advancing
the game or updating memory. Each retry reports the rejection reason in
`reply_error`, plus valid action names for action requests. The tenth failure
stops the program. API and transport errors stop immediately.
Logs, checkpoints, and `progress.txt` are ignored by Git.

[uv]: https://docs.astral.sh/uv/
[Python bindings]: ../bindings/python/README.md
[WebAssembly module]: ../bindings/python/README.md#install-from-source
[config.json.EXAMPLE]: config.json.EXAMPLE
[play.py]: play.py
[agent-instructions.md]: agent-instructions.md
