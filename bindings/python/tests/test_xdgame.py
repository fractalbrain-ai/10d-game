from collections.abc import Callable
from os import environ
from pathlib import Path
from random import Random

import numpy as np
import pytest

import xdgame


@pytest.fixture(scope="session")
def wasm_path() -> Path:
    configured_path = environ.get("XDGAME_WASM_PATH")
    path = (
        Path(configured_path).expanduser()
        if configured_path is not None
        else Path(__file__).parents[3] / "build" / "10d_game.wasm"
    )
    if not path.is_file():
        pytest.fail(
            f"WASM module not found at {path}; build it with `make wasm` or set "
            "XDGAME_WASM_PATH"
        )

    return path


@pytest.fixture(scope="session")
def xdgame_default_config(wasm_path: Path) -> xdgame.Config:
    return xdgame.default_config(wasm_path)


@pytest.fixture(scope="session")
def game_seed() -> int:
    return Random("xdgame test seed").getrandbits(32)


@pytest.mark.parametrize(
    "source_factory",
    [
        lambda path: str(path),
        lambda path: path,
        lambda path: bytearray(path.read_bytes()),
    ],
    ids=["str", "path", "bytearray"],
)
def test_game_loads_from_supported_source_types(
    wasm_path: Path,
    xdgame_default_config: xdgame.Config,
    game_seed: int,
    source_factory: Callable[[Path], str | Path | bytearray],
) -> None:
    with xdgame.Game(
        source_factory(wasm_path), game_seed, xdgame_default_config
    ) as game:
        fov1 = game.fov

        reward = game.tick(xdgame.Action.NOP)
        fov2 = game.fov

        assert np.isfinite(reward)
        assert fov1.tolist() == fov2.tolist()


@pytest.mark.parametrize(
    "bean_variants",
    [
        xdgame.BeanVariants.NO_BEAN_VARIANTS,
        xdgame.BeanVariants.FOUR_BEAN_VARIANTS,
        xdgame.BeanVariants.NINE_BEAN_VARIANTS,
    ],
)
def test_toml_config_roundtrip(
    bean_variants: xdgame.BeanVariants, wasm_path: Path, tmp_path: Path
) -> None:
    config = xdgame.default_config(wasm_path, bean_variants=bean_variants)
    assert config.bean_variants == bean_variants

    toml_file = tmp_path / "config.toml"
    config.to_toml(toml_file)

    assert config == xdgame.config_from_toml(toml_file, wasm=wasm_path)


@pytest.mark.parametrize(
    "bean_variants",
    [
        xdgame.BeanVariants.NO_BEAN_VARIANTS,
        xdgame.BeanVariants.FOUR_BEAN_VARIANTS,
        xdgame.BeanVariants.NINE_BEAN_VARIANTS,
    ],
)
def test_toml_config_overrides(
    bean_variants: xdgame.BeanVariants,
    xdgame_default_config: xdgame.Config,
    wasm_path: Path,
    tmp_path: Path,
) -> None:
    toml_file = tmp_path / "config.toml"
    xdgame_default_config.to_toml(toml_file)

    config = xdgame.config_from_toml(
        toml_file, wasm=wasm_path, bean_variants=bean_variants
    )
    assert config.bean_variants == bean_variants


def test_map_bean_density(wasm_path: Path, game_seed: int):
    config = xdgame.default_config(wasm_path, bean_density=0.5)
    with xdgame.Game(wasm_path, game_seed, config) as game:
        width, height = 100, 100
        world_map = game.generate_map(center=(0, 0), shape=(width, height), time=0)

        occupied = np.any(world_map[..., :2] != 0, axis=-1)
        n_beans = np.count_nonzero(occupied)

        n_cells = width * height
        expected = n_cells * config.bean_density
        std = np.sqrt(n_cells * config.bean_density * (1 - config.bean_density))

        assert n_beans == pytest.approx(expected, abs=5 * std, rel=0)


def test_sun_cycle_duration(
    wasm_path: Path, xdgame_default_config: xdgame.Config, game_seed: int
):
    with xdgame.Game(wasm_path, game_seed, xdgame_default_config) as game:
        width, height = 100, 100

        t1 = 0
        t2 = xdgame_default_config.sun_cycle_duration

        world_map1 = game.generate_map(center=(0, 0), shape=(width, height), time=t1)
        world_map2 = game.generate_map(center=(0, 0), shape=(width, height), time=t2)

        sun1 = world_map1[..., 2]
        sun2 = world_map2[..., 2]

        assert np.unique(sun1).size > 1
        assert sun1 == pytest.approx(sun2, abs=1, rel=0)


def test_gym_environment(wasm_path: Path, game_seed: int) -> None:
    env = xdgame.XDGameEnv(wasm_path, game_seed)
    try:
        assert env.actions() == tuple(xdgame.Action)

        obs1, _ = env.reset()
        assert obs1.keys() == {
            "fov",
            "satiety_level",
            "hydration_level",
            "inventory_count",
        }
        assert obs1["fov"].ndim == 3
        assert obs1["fov"].dtype == np.uint8

        obs2, reward, terminated, truncated, _ = env.step(xdgame.Action.NOP)
        assert obs1["fov"].tolist() == obs2["fov"].tolist()
        assert np.isfinite(reward)
        assert not terminated
        assert not truncated
    finally:
        env.close()
