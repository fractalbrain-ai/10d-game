from enum import IntEnum
from os import PathLike, fspath
from typing import Any, Self, cast
from weakref import finalize

import numpy as np
from numpy.typing import NDArray
from wasmtime import Engine, Func, Instance, Memory, Module, Store

from ._config import CONFIG_SIZE, Config

_U32_MAX = (1 << 32) - 1
_I32_MIN = -(1 << 31)
_I32_MAX = (1 << 31) - 1


class XDGameError(RuntimeError):
    """Indicate that an operation failed inside the 10d_game module."""


class Action(IntEnum):
    """Action applied by :meth:`Game.tick`.

    An action whose requirements are not met behaves like ``NOP``.

    ``NOP``
        Advance time without acting.

    ``MOVE_NORTH``
        Move the agent one world cell north.

    ``MOVE_EAST``
        Move the agent one world cell east.

    ``MOVE_SOUTH``
        Move the agent one world cell south.

    ``MOVE_WEST``
        Move the agent one world cell west.

    ``EAT_BEAN``
        Eat the bean beneath the agent, if present.

    ``PICKUP_BEAN``
        Move the bean beneath the agent into the inventory, if the inventory is
        empty.

    ``DROP_BEAN``
        Place the carried bean beneath the agent, if that world cell is empty.
    """

    NOP = 0
    MOVE_NORTH = 1
    MOVE_EAST = 2
    MOVE_SOUTH = 3
    MOVE_WEST = 4
    EAT_BEAN = 5
    PICKUP_BEAN = 6
    DROP_BEAN = 7


_FUNCTION_EXPORTS = (
    "_initialize",
    "xdgame_default_config",
    "xdgame_free_config",
    "xdgame_new_game",
    "xdgame_free_game",
    "xdgame_generate_map",
    "xdgame_free_map",
    "xdgame_get_map_r",
    "xdgame_get_map_g",
    "xdgame_get_map_b",
    "xdgame_get_map_width",
    "xdgame_get_map_height",
    "xdgame_set_agent",
    "xdgame_tick",
    "xdgame_get_satiety_level",
    "xdgame_get_hydration_level",
    "xdgame_get_inventory_count",
    "xdgame_get_fov_r",
    "xdgame_get_fov_g",
    "xdgame_get_fov_b",
    "xdgame_fov_size",
)


def _wasm_u32(value: int, name: str) -> int:
    if not 0 <= value <= _U32_MAX:
        raise OverflowError(f"{name} must fit in uint32_t")

    return value if value <= _I32_MAX else value - (1 << 32)


def _wasm_i32(value: int, name: str) -> int:
    if not _I32_MIN <= value <= _I32_MAX:
        raise OverflowError(f"{name} must fit in int32_t")

    return value


def _close_wasmtime(store: Store, engine: Engine) -> None:
    try:
        store.close()
    finally:
        engine.close()


def _close_game(runtime: _Runtime, pointer: int) -> None:
    try:
        if runtime.is_open:
            runtime.call("xdgame_free_game", pointer)
    finally:
        runtime.close()


class _Runtime:
    def __init__(
        self,
        wasm: str | PathLike[str] | bytes | bytearray,
    ) -> None:
        self._engine = Engine()

        if isinstance(wasm, (str, PathLike)):
            module = Module.from_file(self._engine, fspath(wasm))
        elif isinstance(wasm, (bytes, bytearray)):
            module = Module(self._engine, bytes(wasm))
        else:
            raise TypeError("wasm must be a path, bytes, or bytearray")

        self._store = Store(self._engine)
        self._finalizer = finalize(self, _close_wasmtime, self._store, self._engine)
        self._instance = Instance(self._store, module, [])
        exports = self._instance.exports(self._store)

        memory = exports["memory"]
        if not isinstance(memory, Memory):
            raise XDGameError("module export 'memory' is not WebAssembly memory")

        self._memory = memory

        self._functions: dict[str, Func] = {}
        for name in _FUNCTION_EXPORTS:
            function = exports[name]
            if not isinstance(function, Func):
                raise XDGameError(f"module export {name!r} is not a function")

            self._functions[name] = function

        self.call("_initialize")

    @property
    def is_open(self) -> bool:
        return self._finalizer.alive

    def call(self, name: str, *arguments: int) -> Any:
        if not self.is_open:
            raise XDGameError("game is closed")

        return self._functions[name](self._store, *arguments)

    def close(self) -> None:
        if self.is_open:
            self._finalizer()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def allocate_config(self, config: Config) -> int:
        pointer = int(self.call("xdgame_default_config"))
        if pointer == 0:
            raise MemoryError("could not allocate xdgame_config_t")

        try:
            self._memory.write(self._store, config._to_bytes(), pointer)
        except BaseException:
            self.call("xdgame_free_config", pointer)
            raise

        return pointer

    def default_config(self, **overrides: object) -> Config:
        pointer = int(self.call("xdgame_default_config"))
        if pointer == 0:
            raise MemoryError("could not allocate xdgame_config_t")
        try:
            data = self._memory.read(self._store, pointer, pointer + CONFIG_SIZE)
            config = Config._from_bytes(data)
        finally:
            self.call("xdgame_free_config", pointer)
        return config._with_overrides(overrides)

    def read_rgb(
        self,
        pointer: int,
        width: int,
        height: int,
        red_export: str,
        green_export: str,
        blue_export: str,
    ) -> NDArray[np.uint8]:
        pixel_count = width * height
        channels = []
        for export in (red_export, green_export, blue_export):
            channel_pointer = int(self.call(export, pointer))
            data = self._memory.read(
                self._store, channel_pointer, channel_pointer + pixel_count
            )
            channels.append(np.frombuffer(data, dtype=np.uint8).reshape(height, width))

        return cast(NDArray[np.uint8], np.stack(channels, axis=-1))


def default_config(
    wasm: str | PathLike[str] | bytes | bytearray,
    **overrides: object,
) -> Config:
    """Load the game engine's default configuration.

    Keyword arguments replace individual values after the configuration is read
    from the WebAssembly module. The returned configuration is independent of
    the temporary runtime used to obtain it. Use field names from
    :class:`Config` as keyword names.

    :param wasm: Path to a ``10d_game.wasm`` file or its in-memory contents.
    :param overrides: Configuration fields to replace.
    :return: Game-engine defaults with the requested replacements applied.
    :raises TypeError: If ``wasm`` or an override has an invalid type.
    :raises ValueError: If an override value is outside its valid range.
    :raises MemoryError: If the module cannot allocate the configuration.
    """
    with _Runtime(wasm) as runtime:
        return runtime.default_config(**overrides)


def config_from_toml(
    path: str | PathLike[str],
    *,
    wasm: str | PathLike[str] | bytes | bytearray,
    **overrides: object,
) -> Config:
    """Load a configuration from game-engine defaults and a TOML file.

    Values from the TOML file replace game-engine defaults read from ``wasm``.
    Keyword arguments are applied last and therefore take precedence over both
    the engine defaults and TOML values.

    :param path: Path to a TOML configuration file. Fields may be omitted.
    :param wasm: Path to a ``10d_game.wasm`` file or its in-memory contents.
    :param overrides: Configuration fields to replace after reading TOML.
    :return: The merged and validated configuration.
    :raises OSError: If the TOML file cannot be read.
    :raises TypeError: If ``wasm``, a field, or an override has an invalid type.
    :raises ValueError: If the TOML is malformed, contains an unknown field, or
        contains a value outside its valid range.
    :raises MemoryError: If the module cannot allocate its defaults.
    """
    config = default_config(wasm)._with_toml(path)
    return config._with_overrides(overrides)


class Game:
    """Load a 10d_game WebAssembly module and own one game instance.

    ``wasm`` may be a filesystem path or in-memory WebAssembly bytes. Immutable
    :class:`bytes` are preferred for in-memory modules; :class:`bytearray` is
    accepted for convenience and copied during construction.

    If ``config`` is omitted, the defaults from the supplied engine are used.
    The engine copies a supplied configuration during construction, so that
    configuration remains independent of the game.

    Use the object as a context manager or call :meth:`close` when finished.
    Public operations other than :meth:`close` raise :class:`XDGameError` after
    the game has been closed.

    :param wasm: Path to a ``10d_game.wasm`` file or its in-memory contents.
    :param seed: Unsigned 32-bit world seed. Zero is valid.
    :param config: Configuration obtained from :func:`default_config` or
        :func:`config_from_toml`. Omit it to use game-engine defaults.
    :raises TypeError: If ``wasm`` is not a supported path or byte container.
    :raises OverflowError: If ``seed`` does not fit in ``uint32_t``.
    :raises MemoryError: If a required allocation fails.
    :raises XDGameError: If the module is incompatible or the game cannot be
        created.
    """

    def __init__(
        self,
        wasm: str | PathLike[str] | bytes | bytearray,
        seed: int,
        config: Config | None = None,
    ) -> None:
        wasm_seed = _wasm_u32(seed, "seed")
        runtime = _Runtime(wasm)
        try:
            if config is None:
                config = runtime.default_config()

            config_pointer = runtime.allocate_config(config)
            try:
                pointer = int(
                    runtime.call("xdgame_new_game", wasm_seed, config_pointer)
                )
            finally:
                runtime.call("xdgame_free_config", config_pointer)

            if pointer == 0:
                raise XDGameError(
                    "could not create game: invalid config or allocation failure"
                )
        except BaseException:
            runtime.close()
            raise

        self._runtime = runtime
        self._pointer: int | None = pointer
        self._finalizer = finalize(self, _close_game, runtime, pointer)

    def _require_pointer(self) -> int:
        if self._pointer is None:
            raise XDGameError("game is closed")

        return self._pointer

    def close(self) -> None:
        """Free the game and all generated world data.

        Calling this method more than once has no effect.
        """
        if self._pointer is not None:
            try:
                self._finalizer()
            finally:
                self._pointer = None

    def __enter__(self) -> Self:
        self._require_pointer()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def set_agent(self, x: int, y: int) -> None:
        """Place the agent at a world position.

        The agent's field of view is refreshed around the new position, with
        required world patches generated as necessary. If the operation fails,
        the agent position and field of view remain unchanged.

        :param x: Horizontal world coordinate.
        :param y: Vertical world coordinate.
        :raises OverflowError: If either coordinate does not fit in ``int32_t``.
        :raises XDGameError: If the game is closed or the position cannot be set.
        """
        success = self._runtime.call(
            "xdgame_set_agent",
            self._require_pointer(),
            _wasm_i32(x, "x"),
            _wasm_i32(y, "y"),
        )
        if not success:
            raise XDGameError("could not set agent position")

    def tick(self, action: Action | int) -> float:
        """Advance the game by one tick.

        The action, resource decay, delayed salty-bean effects, and reward are
        evaluated at the current tick before the internal time is incremented.
        Invalid or inapplicable actions behave like ``NOP`` from
        :class:`xdgame.Action`.

        :param action: Action to apply during the tick.
        :return: Reward produced by the tick.
        :raises OverflowError: If an integer action does not fit in ``int32_t``.
        :raises XDGameError: If the game is closed.
        """
        return float(
            self._runtime.call(
                "xdgame_tick",
                self._require_pointer(),
                _wasm_i32(int(action), "action"),
            )
        )

    @property
    def satiety_level(self) -> float:
        """Current satiety level.

        The level starts at 100, changes each tick according to the
        :class:`xdgame.Config` value ``needs_decay``, is affected by beans, and
        remains between -100 and 100.

        :raises XDGameError: If the game is closed.
        """
        return float(
            self._runtime.call("xdgame_get_satiety_level", self._require_pointer())
        )

    @property
    def hydration_level(self) -> float:
        """Current hydration level.

        The level starts at 100, changes each tick according to the
        :class:`xdgame.Config` value ``needs_decay``, is affected by beans, and
        remains between -100 and 100.

        :raises XDGameError: If the game is closed.
        """
        return float(
            self._runtime.call("xdgame_get_hydration_level", self._require_pointer())
        )

    @property
    def inventory_count(self) -> int:
        """Number of beans currently carried by the agent.

        The inventory holds at most one bean, so the value is either zero or
        one.

        :raises XDGameError: If the game is closed.
        """
        return int(
            self._runtime.call("xdgame_get_inventory_count", self._require_pointer())
        )

    @property
    def fov(self) -> NDArray[np.uint8]:
        """Copy the current field of view into an RGB array.

        The returned :class:`numpy.ndarray` has dtype :class:`numpy.uint8` and
        shape ``(height, width, 3)``. Row zero represents the lowest visible
        world y-coordinate. The agent occupies the center pixel but is not
        drawn into the image. Obtain the dimensions with
        ``height, width, channels = game.fov.shape``.

        Each access returns an independent copy that remains valid after later
        ticks, agent movements, or game closure.

        :raises XDGameError: If the game is closed.
        """
        side = int(self._runtime.call("xdgame_fov_size", 0))
        return self._runtime.read_rgb(
            self._require_pointer(),
            side,
            side,
            "xdgame_get_fov_r",
            "xdgame_get_fov_g",
            "xdgame_get_fov_b",
        )

    def generate_map(
        self,
        *,
        center: tuple[int, int],
        shape: tuple[int, int],
        time: int = 0,
    ) -> NDArray[np.uint8]:
        """Generate an RGB map snapshot.

        The returned array has shape ``(height, width, 3)`` and dtype
        :class:`numpy.uint8`. Row zero represents the lowest world y-coordinate
        covered by the map.

        :param center: Map-center world coordinates in ``(x, y)`` order.
        :param shape: Map dimensions in NumPy ``(height, width)`` order. Both
            dimensions must be positive.
        :param time: Tick at which sunlight is evaluated.
        :return: A copied RGB map that remains valid independently of the game.
        :raises OverflowError: If a coordinate, dimension, or time does not fit
            its corresponding C integer type.
        :raises XDGameError: If the game is closed or the map cannot be generated.
        """
        center_x, center_y = center
        height, width = shape
        map_pointer = int(
            self._runtime.call(
                "xdgame_generate_map",
                self._require_pointer(),
                _wasm_i32(center_x, "center_x"),
                _wasm_i32(center_y, "center_y"),
                _wasm_u32(width, "width"),
                _wasm_u32(height, "height"),
                _wasm_u32(time, "time"),
            )
        )
        if map_pointer == 0:
            raise XDGameError(
                "could not generate map: invalid bounds or allocation failure"
            )

        try:
            map_width = int(self._runtime.call("xdgame_get_map_width", map_pointer))
            map_height = int(self._runtime.call("xdgame_get_map_height", map_pointer))
            return self._runtime.read_rgb(
                map_pointer,
                map_width,
                map_height,
                "xdgame_get_map_r",
                "xdgame_get_map_g",
                "xdgame_get_map_b",
            )
        finally:
            self._runtime.call("xdgame_free_map", map_pointer)
