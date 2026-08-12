# 10d-game

[![Play in browser](https://img.shields.io/badge/play-in%20browser-2f855a)](https://fractal-brain-ai.github.io/10d-game/)
[![C API documentation](https://img.shields.io/badge/docs-C%20API-00e5ff)](https://fractal-brain-ai.github.io/10d-game/c-api/)
[![Python documentation](https://img.shields.io/badge/docs-Python-3776ab)](https://fractal-brain-ai.github.io/10d-game/python/)

10d-game is a small C game engine intended for AI-agent experiments. An agent
observes a square field of view and chooses one action per tick from a compact
action space. The procedurally generated world contains four bean flavors that
affect satiety, hydration, or reward. Given the same seed, configuration, and
actions, the engine produces the same world and game evolution.

The engine is deliberately independent of a particular user interface. It can
be embedded directly through its C API, loaded as WebAssembly, controlled from
Python, or explored through the self-contained browser interface.

## Portability and distribution

The C library has no external dependencies beyond the C standard library and
math library, and it also works on 32-bit systems. Applications can therefore
compile and link it directly with their C compiler, for example:

```bash
$CC -std=c23 -O3 -c 10d_game.c
$CC your_program.c 10d_game.o -lm
```

Alternatively, each tagged release provides a compiled
[`10d_game.wasm` module](https://github.com/fractal-brain-ai/10d-game/releases/latest/download/10d_game.wasm).
The [Python binding](bindings/python) loads this module through Wasmtime rather
than compiling a platform-specific extension, which keeps the binding highly
portable across platforms supported by its runtime.

The same WASM module is also bundled with the browser interface into a single,
self-contained HTML file. You can
[play 10d-game directly in your browser](https://fractal-brain-ai.github.io/10d-game/)
without installing anything or running a server.

## Engine files

- [`10d_game.h`](10d_game.h) defines the public C API. It contains the game
  configuration, available actions, lifecycle functions, state getters, field
  of view accessors, and map-generation interface. Its API documentation also
  explains the bean effects, sunlight parameters, and image-channel layout.

- [`10d_game.c`](10d_game.c) implements the engine. It contains deterministic
  world and patch generation, bean placement and coloring, sunlight rendering,
  agent actions, resource levels, rewards, and field of view generation.

## Bindings and interfaces

- [`bindings/browser/10d_game.html`](bindings/browser/10d_game.html) is the
  source template for the browser interface. The build embeds the compiled
  WebAssembly module together with all JavaScript and CSS into one HTML file.
  The result can be opened directly from disk without a web server. It provides
  a simple human interface for observing the field of view and controlling the
  agent. The latest tagged release is also available as a
  [hosted browser game](https://fractal-brain-ai.github.io/10d-game/).

- [`bindings/python`](bindings/python) contains the Python binding. It loads the
  WebAssembly module through Wasmtime, exposes a Python API, returns images as
  NumPy arrays, and provides command-line tools for rendering maps and
  controlling an agent. Installation, usage, testing, and documentation
  instructions are in the dedicated
  [Python binding README](bindings/python/README.md).

## Development

### Set up Emscripten

The project uses the [Emscripten SDK
(emsdk)](https://emscripten.org/docs/tools_reference/emsdk.html) to compile the
C engine to WebAssembly. The Makefile expects it at the repository-relative
path `3rd-party/emsdk/upstream/emscripten/emcc`. Run all commands in this
section from the repository root so that this path resolves correctly.

First, initialize the official [emsdk Git
repository](https://github.com/emscripten-core/emsdk) included as a submodule:

```bash
git submodule update --init --recursive
```

Then install and activate the SDK selected by the checked-out emsdk version:

```bash
./3rd-party/emsdk/emsdk install latest
./3rd-party/emsdk/emsdk activate latest
```

Activation creates the local emsdk configuration needed by `emcc`. The
Makefile invokes `emcc` through its explicit repository-relative path, so it
does not depend on `emcc` being present in `PATH` and does not require sourcing
`emsdk_env.sh` before each build.

### Build the WebAssembly module

Build the engine as a standalone WebAssembly module with:

```bash
make wasm
```

The result is written to `build/10d_game.wasm`. The default `make` target is
also `wasm`.

### Build the browser interface

Build the self-contained browser interface with:

```bash
make html
```

This builds the WebAssembly module when necessary, encodes it into the HTML
template, and writes `build/10d_game.html`. Open that file directly in a modern
browser. A seed can also be supplied through the URL, for example:

```text
file:///path/to/10d_game/build/10d_game.html?seed=1234
```

### Check and format the C sources

The C checks require `clang-format` and `clang-tidy`:

```bash
make check
```

Format the C source and header in place with:

```bash
make format
```

Remove generated build artifacts with:

```bash
make clean
```
