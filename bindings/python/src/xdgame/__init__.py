"""
``xdgame`` runs the 10d_game engine through a caller-supplied WebAssembly
module.

Overview
--------

The Python package is a wrapper around the compiled 10d_game engine. The engine
itself lives in a WebAssembly (WASM) file and implements world generation, game
state, actions, rewards, fields of view, and map snapshots. The package does not
bundle that file: callers select the engine binary they want to run and pass
its path or in-memory contents to :class:`Game`.

The public API centers on three objects:

* :class:`Config` contains the parameters used to create a game, such as bean
  density, bean effects, and sunlight behavior. Game-engine defaults are read
  from a caller-supplied WASM file.
* :class:`Game` loads the WASM engine and owns the mutable state of one
  deterministic game run. Use it as a context manager to release both the game
  state and Wasmtime runtime promptly.
* :class:`XDGameEnv` owns one :class:`Game` and presents its actions,
  observations, and rewards through the Gym environment protocol without
  depending on Gym itself. The environment is a continuing task and never
  terminates or truncates itself.

Getting started
---------------

Pass the WASM engine and a seed directly to :class:`Game`. If no configuration
is supplied, the game-engine defaults are used.

.. code-block:: python

   import xdgame

   with xdgame.Game("build/10d_game.wasm", seed=42) as game:
       reward = game.tick(xdgame.Action.MOVE_NORTH)
       field_of_view = game.fov
       world_map = game.generate_map(center=(0, 0), shape=(256, 256))

The ``field_of_view`` and ``world_map`` are copied into RGB :class:`numpy.ndarray`
objects with dtype :class:`numpy.uint8` and shape ``(height, width, 3)``. Row zero
represents the lowest visible world y-coordinate.

Gym-style interaction
---------------------

Besides :class:`Game`, xdgame also provides a Gym-style API through
:class:`XDGameEnv`, with the canonical ``reset()``, ``step()``, and ``close()``
functions. Its observations contain the FoV, satiety level, hydration level,
and inventory count. Use :meth:`XDGameEnv.actions` to inspect all accepted
actions. After each step, the information dictionary reports which bean flavor
was eaten. This is privileged evaluation information: it is not part of the
observation and must not be used by the agent to select actions.

.. code-block:: python

   env = xdgame.XDGameEnv("build/10d_game.wasm", seed=42)
   try:
       actions = env.actions()
       observation, info = env.reset()
       observation, reward, terminated, truncated, info = env.step(
           xdgame.Action.MOVE_NORTH
       )
   finally:
       env.close()

The task is intentionally infinite, so ``terminated`` and ``truncated`` are
always false. Call :meth:`XDGameEnv.reset` at any time to restore the
environment to its initial state.

Evaluation information
~~~~~~~~~~~~~~~~~~~~~~

:meth:`XDGameEnv.step` reports the bean flavor eaten during the transition in
``info["eaten_bean_flavor"]``. The value is ``"satiety"``, ``"hydration"``,
``"salty"``, or ``"bitter"`` when a bean was eaten, and ``None`` otherwise.

This value is privileged evaluation information. It is not part of the
observation and must not be used by the agent to select actions. Code using
:class:`Game` directly can reveal the same value with
:meth:`Game.reveal_last_eaten_flavor`.

Game configuration and TOML
---------------------------

A :class:`Config` describes how new games are initialized and how their world,
beans, resource effects, and sunlight behave. It does not contain mutable game
state and is not a saved game run.

:func:`default_config` reads the game-engine defaults from a WASM file and can
apply keyword overrides. For a human-editable configuration,
:func:`config_from_toml` starts with those same defaults, applies every value
present in the TOML file, and finally applies keyword overrides. A TOML file may
therefore be partial: omitted fields retain their game-engine default.

.. code-block:: python

   config = xdgame.config_from_toml(
       "xdgame-config.toml",
       wasm="build/10d_game.wasm",
       bean_density=0.05,
   )

Conversely, :meth:`Config.to_toml` writes every field of a configuration and
provides a convenient starting point for editing:

.. code-block:: python

   config = xdgame.default_config("build/10d_game.wasm")
   config.to_toml("xdgame-config.toml")
"""

from ._config import BeanVariants, Config
from ._gym import XDGameEnv
from ._runtime import Action, Game, XDGameError, config_from_toml, default_config

__all__ = [
    "Action",
    "BeanVariants",
    "Config",
    "Game",
    "XDGameEnv",
    "XDGameError",
    "config_from_toml",
    "default_config",
]
