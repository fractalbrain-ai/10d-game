from os import PathLike

import numpy as np
from numpy.typing import NDArray

from ._config import Config
from ._runtime import Action, Game, XDGameError


class XDGameEnv:
    """Expose one :class:`xdgame.Game` through the Gym environment protocol.

    This class provides the canonical :meth:`reset`, :meth:`step`, and
    :meth:`close` functions. Actions are the integer values of
    :class:`xdgame.Action`.

    The observation is a dictionary containing the raw field of view and the
    agent's three remaining observable state values. Its keys are ``"fov"``,
    ``"satiety_level"``, ``"hydration_level"``, and ``"inventory_count"``.
    Satiety and hydration are :class:`float` values; the inventory count is
    either zero or one.

    The environment represents a continuing, deliberately infinite task.
    Consequently, :meth:`step` always returns ``False`` for both
    ``terminated`` and ``truncated``. Call :meth:`reset` at any time to restore
    the environment to its initial state. Consumers that need finite training
    sequences must impose that boundary themselves without interpreting it as
    an engine-defined terminal state.

    The FoV contains the engine's raw three channels and is not converted to
    display colors.

    :param wasm: Path to a ``10d_game.wasm`` file or its in-memory contents.
    :param seed: Unsigned 32-bit world seed.
    :param config: Game configuration. Omit it to use the engine defaults.
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
        self._wasm = bytes(wasm) if isinstance(wasm, bytearray) else wasm
        self._seed = seed
        self._config = config
        self._game: Game | None = Game(self._wasm, seed, config)

    def _require_game(self) -> Game:
        if self._game is None:
            raise XDGameError("environment is closed")

        return self._game

    def _get_observation(
        self,
    ) -> dict[str, NDArray[np.uint8] | float | int]:
        game = self._require_game()
        return {
            "fov": game.fov,
            "satiety_level": game.satiety_level,
            "hydration_level": game.hydration_level,
            "inventory_count": game.inventory_count,
        }

    @staticmethod
    def actions() -> tuple[Action, ...]:
        """Return all actions accepted by :meth:`step`.

        The tuple follows the actions' integer encoding order. Every action is
        always accepted, but an action whose requirements are not met behaves
        like ``NOP`` from :class:`xdgame.Action`.

        :return: Complete action tuple in integer encoding order.
        """
        return tuple(Action)

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, object] | None = None,
    ) -> tuple[
        dict[str, NDArray[np.uint8] | float | int],
        dict[str, object],
    ]:
        """Restore the initial state and procedurally generated world.

        With no ``seed``, the world is recreated from the seed passed to the
        constructor or the most recent explicit reset seed. Passing a seed
        selects that seed for this and subsequent resets. ``options`` is
        accepted for Gym compatibility but currently ignored.

        :param seed: Optional unsigned 32-bit world seed.
        :param options: Reserved for future reset options.
        :return: The initial observation and an empty information dictionary.
        :raises OverflowError: If ``seed`` does not fit in ``uint32_t``.
        :raises XDGameError: If the environment is closed or the new game
            cannot be created.
        """
        del options
        self._require_game()

        world_seed = self._seed if seed is None else seed
        new_game = Game(self._wasm, world_seed, self._config)
        old_game = self._require_game()
        self._game = new_game
        self._seed = world_seed
        old_game.close()
        return self._get_observation(), {}

    def step(
        self,
        action: int,
    ) -> tuple[
        dict[str, NDArray[np.uint8] | float | int],
        float,
        bool,
        bool,
        dict[str, object],
    ]:
        """Apply one action and return the resulting transition.

        This environment has no terminal state or time limit, so the returned
        ``terminated`` and ``truncated`` values are always ``False``.

        :param action: Integer value corresponding to a member of
            :class:`xdgame.Action`.
        :return: Observation, reward, ``False``, ``False``, and an empty
            information dictionary.
        :raises TypeError: If ``action`` is not an integer.
        :raises ValueError: If ``action`` is not a defined
            :class:`xdgame.Action` value.
        :raises XDGameError: If the environment is closed.
        """
        if not isinstance(action, (int, np.integer)):
            raise TypeError("action must be an integer")

        try:
            game_action = Action(int(action))
        except ValueError as error:
            raise ValueError(f"invalid action: {action!r}") from error

        reward = self._require_game().tick(game_action)
        return self._get_observation(), reward, False, False, {}

    def close(self) -> None:
        """Release the underlying game and WebAssembly runtime.

        Calling this method more than once has no effect. After it is called,
        :meth:`reset` and :meth:`step` raise :class:`xdgame.XDGameError`.
        """
        if self._game is not None:
            self._game.close()
            self._game = None
