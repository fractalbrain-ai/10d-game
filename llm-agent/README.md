# 10d-game LLM agent

This directory provides a headless runner for studying how language-model
agents learn the mechanics of 10d-game through observations and rewards.
[play.py] runs the game through the [Python bindings] and sends observations
directly to an OpenAI-compatible model server, whose replies choose one action
at a time. After each episode, the model summarizes what it has learned into
memory that carries over to the next episode while the game continues.

The agent has no access to tools and follows [agent-instructions.md], which
defines its objective, observations, available actions, and response format.
You can edit that file to change the instructions supplied to the model.

## Setup

The runner requires [uv], Python 3.14 or newer, and a compiled
[WebAssembly module], which you can obtain by following the [Python bindings]
instructions. The commands below assume you are in the repository root and
have placed the module at `build/10d_game.wasm`; if you keep it elsewhere,
supply its path with `--wasm` when launching the runner.

Create your local model configuration by copying the supplied example:

```bash
cp llm-agent/config.json.EXAMPLE llm-agent/config.json
```

In the new `config.json`, set `api_base` for your model server and adjust
`completion` for your model. The supplied example targets Qwen served through
vLLM, so its generation parameters may need adjustment for other servers
because the runner sends them unchanged.

The server must accept non-streaming Chat Completions requests with Bearer
authentication and text system/user/assistant messages, and return the standard
response with `finish_reason: "stop"`. The model must follow the JSON response
formats in [agent-instructions.md]. If you use a reasoning model, the server
must also accept and retain reasoning fields in historical assistant messages,
as enabled by Qwen's `preserve_thinking` setting in the example configuration.

Although your local `config.json` is ignored by Git by default, we recommend
keeping the API key out of the file and supplying it through an environment
variable instead. The runner supports this through `api_key_env`, which names the
variable to read: the example configuration uses `MODEL_API_KEY`, but you can
choose another name. With that example configuration, export your key in the
shell where you will launch the runner:

```bash
export MODEL_API_KEY='your-api-key'
```

This lookup is specific to `api_key_env`; other configuration values are read
literally, without environment-variable substitution. If you prefer to store
the key in the file, remove `api_key_env` and set `api_key` instead.

## Run

Launch the runner through the Python binding's [uv] environment. For example,
the following command starts a game with seed 42 and runs one 25-step episode:

```bash
uv run --project bindings/python llm-agent/play.py --seed 42 --steps 25
```

The required `--steps` argument sets the total number of game actions, rounded
up to a multiple of the episode length selected by `--in-context-steps`
(default: 25). For example, `--steps 30 --in-context-steps 25` runs 50 actions
across two episodes. Within each episode, the model retains all observations
and complete accepted replies, including reasoning, before making one extra
summary call that does not advance the game. Only the resulting memory carries
into the next episode, so choose an episode length that leaves room in the
model's context window for its reasoning, memory, and next reply.

If a reply is invalid, the runner asks the model to correct it by supplying
the rejection reason in `reply_error`, along with the valid action names for
action requests. It allows up to ten attempts per action or summary without
advancing the game or updating memory, then stops if no valid reply is
received; API and transport errors stop the run immediately. Add `--help` to
the command above to see all options, including alternate configuration and
instruction files.

## Recorded output

Every invocation creates a fresh directory under `llm-agent/logs/`, using the
current UTC time as its name. For example, a run started at 14:30:52 UTC on
November 17, 2026 would produce the following files after successful completion:

```text
llm-agent/logs/
└── 20261117T143052Z/
    ├── log.jsonl
    └── checkpoint.json
```

The runner writes model requests, responses, game transitions, and summaries
to `log.jsonl` as it progresses, then saves the seed, action history, and final
memory to `checkpoint.json` when it finishes successfully. The output directory
and file layout are printed at startup and again at completion; interrupted or
failed runs retain their logs but do not produce a new checkpoint. If a
directory name is already taken, a suffix such as `-2` or `-3` keeps the new
run's output separate from earlier or simultaneous runs.

Standard output is for human amusement: reasoning, replies, and progress
banners let you watch the model at work, while `log.jsonl` already contains
the model exchanges and game transitions needed to analyze the run. Saving
this console output is entirely optional; unhandled exceptions go to stderr.

If you would also like a readable file for a quick look at progress, `tee`
can keep displaying stdout while saving a copy. For convenience, `progress.txt`
is ignored by Git by default, alongside the generated run directories. For
example, the following command runs 100 steps and creates an additional
readable transcript at `llm-agent/progress.txt`:

```bash
uv run --project bindings/python llm-agent/play.py --seed 42 --steps 100 \
    | tee -i llm-agent/progress.txt
```

## Continue a run

To continue a completed run, pass its `checkpoint.json` path with `--checkpoint`.
The runner restores the saved seed and memory and replays the recorded actions
without model calls, so use the same engine and game configuration to recover
the same game state. The `--steps` argument still specifies the total number
of actions, including those replayed from the checkpoint, and must exceed the
number already recorded.

For example, if the directory shown above contains a completed 25-step run,
the following command replays those 25 actions and performs 25 new ones to
reach a total of 50:

```bash
uv run --project bindings/python llm-agent/play.py \
    --checkpoint llm-agent/logs/20261117T143052Z/checkpoint.json \
    --steps 50
```

The resumed invocation writes its log and new checkpoint to a fresh run
directory, preserving the files from the earlier run. If the loaded checkpoint
ends between episode boundaries, the first resumed episode ends at the next
multiple of `--in-context-steps`, after which full-length episodes continue.

[uv]: https://docs.astral.sh/uv/
[Python bindings]: ../bindings/python/README.md
[WebAssembly module]: ../bindings/python/README.md#install-from-source
[config.json.EXAMPLE]: config.json.EXAMPLE
[play.py]: play.py
[agent-instructions.md]: agent-instructions.md
