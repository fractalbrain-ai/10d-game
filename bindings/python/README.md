# 10d-game Python bindings

[![Python documentation](https://img.shields.io/badge/docs-Python-3776ab)](https://fractal-brain-ai.github.io/10d-game/python/)

The `xdgame` package provides Python bindings for the 10d-game engine. It loads
the engine as a WebAssembly module through [Wasmtime](https://wasmtime.dev/) and
exposes its configuration, game state, and generated images through a
Python-friendly API. Fields of view and rendered maps are returned as NumPy
arrays.

The WebAssembly module is supplied when creating an `xdgame.Game`, so the same
Python package can be used with different builds of the engine.

## Install from source

The bindings require Python 3.14 or newer and
use [uv](https://docs.astral.sh/uv/)
for environment and dependency management.

First, build the WebAssembly module from the repository root:

```bash
make wasm
```

This creates `build/10d_game.wasm`, which callers pass to the Python binding
when loading the engine. Alternatively, download
[`10d_game.wasm` from the latest tagged release](https://github.com/fractal-brain-ai/10d-game/releases/latest/download/10d_game.wasm).
Then create a virtual environment and install the Python package:

```bash
cd bindings/python
uv venv
uv pip install .
```

## Quick example

The following example creates a game from the engine defaults, advances it by
one tick, and obtains both the agent's field of view and a larger rendered map:

```python
from pathlib import Path

import xdgame

wasm_path = Path("build/10d_game.wasm")
with xdgame.Game(wasm_path, seed=42) as game:
    reward = game.tick(xdgame.Action.NOP)
    fov = game.fov
    map_image = game.generate_map(
        center=(0, 0),
        shape=(256, 256),
        time=0,
    )

print(f"reward: {reward}")
print(f"field of view: {fov.shape}")
print(f"map: {map_image.shape}")
```

Run the example from the repository root so that the relative path to the
WebAssembly module resolves correctly. Both images have the shape
`(height, width, 3)` and the data type `numpy.uint8`.

## Render a map from the command line

The game world is generated procedurally and deterministically from its seed and
configuration. Its generation does not depend on how the agent moves:
given the same seed and configuration, an agent encounters the same world in the
same places. The agent changes the world only by removing beans when eating or
picking them up, and by placing carried beans when dropping them.

The package installs `xdgame-render-map`, a command-line tool for investigating
this procedurally generated world without moving an agent through it. It renders
a selected region to a PNG file. From `bindings/python`, run:

```bash
uv run xdgame-render-map \
    ../../build/10d_game.wasm \
    map.png \
    --seed 42 \
    --width 512 \
    --height 512
```

The map is centered at world position `(0, 0)` and rendered at time zero by
default. The PNG records the seed, center coordinates, dimensions, and time in
`xdgame.*` text metadata fields. Use `--center X Y` or `--time T` to select
different values. A TOML configuration can be supplied with `--config`:

```bash
uv run xdgame-render-map \
    ../../build/10d_game.wasm \
    map.png \
    --config game-engine-config.toml \
    --seed 42 \
    --width 512 \
    --height 512
```

To create a TOML file containing the game engine's default configuration, use:

```bash
uv run xdgame-render-map \
    ../../build/10d_game.wasm \
    --write-default-config game-engine-config.toml
```

Run `uv run xdgame-render-map --help` for the complete command-line reference.

## Control an agent

The optional graphical interface lets a human control an agent one action at a
time. Install its dependency from `bindings/python`:

```bash
uv pip install ".[gui]"
```

The WebAssembly module and world seed are required at startup. Without a
configuration file, the game-engine defaults are used:

```bash
uv run --extra gui xdgame-play \
    ../../build/10d_game.wasm \
    --seed 42
```

Use `--config game-engine-config.toml` to overwrite the defaults with values
from a TOML file. All startup options are command-line arguments; the interface
does not provide in-game loading.

The window displays the field of view, satiety and hydration levels, inventory
state, cumulative reward, and all available actions. Use `W`, `A`, `S`, and `D`
or the arrow keys to move, `E` to eat, `F` to pick up a bean, `R` to drop it,
and Space to wait. Hold a movement key or Space for 500 ms to repeat that action
at 10 Hz. Press `Q` or Escape to quit.

## Development

Install the project together with its development dependencies from
`bindings/python`:

```bash
uv sync --group dev
uv run --group dev pre-commit install
```

The installed pre-commit hooks run Ruff and the pytest suite before each
commit. Run both hooks manually against the complete repository with:

```bash
uv run --group dev pre-commit run --all-files
```

The pytest hook expects the WebAssembly module at `../../build/10d_game.wasm`.
Set `XDGAME_WASM_PATH` to use a module stored elsewhere; the same override is
used by direct pytest runs:

```bash
XDGAME_WASM_PATH=/path/to/10d_game.wasm uv run --group dev pytest
```

To skip the test suite for one commit, set pre-commit's `SKIP` environment
variable to the hook ID:

```bash
SKIP=pytest git commit
```

Build the WebAssembly module and run the test suite:

```bash
cd ../..
make wasm
cd bindings/python
uv run --group dev pytest
```

To build the Sphinx documentation, install the documentation dependencies and
run Sphinx with warnings treated as errors:

```bash
uv sync --group docs
uv run --group docs sphinx-build -W -b html docs docs/_build/html
```

The generated documentation starts at `docs/_build/html/index.html`.
