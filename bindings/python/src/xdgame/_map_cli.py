import argparse
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from ._runtime import Game, config_from_toml, default_config

_UINT32_MAX = (1 << 32) - 1
_INT32_MIN = -(1 << 31)
_INT32_MAX = (1 << 31) - 1


def _validate_output_path(
    parser: argparse.ArgumentParser,
    path: Path,
    argument: str,
) -> None:
    if path.exists() and not path.is_file():
        parser.error(f"{argument} must name a regular file: {path}")

    if not path.parent.is_dir():
        parser.error(f"parent directory does not exist for {argument}: {path.parent}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="xdgame-render-map",
        description="Generate a PNG map from a 10d_game WebAssembly module.",
    )
    parser.add_argument("wasm", type=Path, help="path to 10d_game.wasm")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="path of the PNG to create",
    )
    parser.add_argument(
        "--write-default-config",
        type=Path,
        metavar="PATH",
        help="write the game engine's default configuration as TOML and exit",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="TOML configuration file (default: game-engine defaults)",
    )
    parser.add_argument("--seed", type=int, help="world seed")
    parser.add_argument(
        "--center",
        type=int,
        nargs=2,
        metavar=("X", "Y"),
        help="world coordinates at the center of the map (default: 0 0)",
    )
    parser.add_argument("--width", type=int, help="map width in cells")
    parser.add_argument("--height", type=int, help="map height in cells")
    parser.add_argument("--time", type=int, help="map time in ticks (default: 0)")

    args = parser.parse_args(argv)

    if args.write_default_config is not None:
        conflicts = [
            name
            for name, value in (
                ("output", args.output),
                ("--config", args.config),
                ("--seed", args.seed),
                ("--center", args.center),
                ("--width", args.width),
                ("--height", args.height),
                ("--time", args.time),
            )
            if value is not None
        ]
        if conflicts:
            parser.error(
                "--write-default-config cannot be combined with " + ", ".join(conflicts)
            )

        _validate_output_path(
            parser,
            args.write_default_config,
            "--write-default-config",
        )
        try:
            default_config(args.wasm).to_toml(args.write_default_config)
        except OSError as error:
            parser.exit(
                1,
                f"{parser.prog}: error: could not write "
                f"{args.write_default_config}: {error}\n",
            )
        return

    if args.output is None:
        parser.error("output is required unless --write-default-config is used")

    missing_options = [
        name
        for name, value in (
            ("--seed", args.seed),
            ("--width", args.width),
            ("--height", args.height),
        )
        if value is None
    ]
    if missing_options:
        parser.error(
            "the following arguments are required: " + ", ".join(missing_options)
        )

    center = args.center if args.center is not None else (0, 0)
    time = args.time if args.time is not None else 0

    if not 0 <= args.seed <= _UINT32_MAX:
        parser.error("--seed must fit in uint32_t")

    if not 1 <= args.width <= _UINT32_MAX:
        parser.error("--width must be between 1 and 4294967295")

    if not 1 <= args.height <= _UINT32_MAX:
        parser.error("--height must be between 1 and 4294967295")

    if not 0 <= time <= _UINT32_MAX:
        parser.error("--time must fit in uint32_t")

    if any(coordinate < _INT32_MIN or coordinate > _INT32_MAX for coordinate in center):
        parser.error("--center coordinates must fit in int32_t")

    _validate_output_path(parser, args.output, "output")

    if args.config is None:
        config = None
    else:
        try:
            config = config_from_toml(args.config, wasm=args.wasm)
        except (OSError, TypeError, ValueError) as error:
            parser.error(f"invalid --config: {error}")

    with Game(args.wasm, args.seed, config) as game:
        image = game.generate_map(
            center=(center[0], center[1]),
            shape=(args.height, args.width),
            time=time,
        )

    metadata = PngInfo()
    metadata.add_text("xdgame.seed", str(args.seed))
    metadata.add_text("xdgame.center_x", str(center[0]))
    metadata.add_text("xdgame.center_y", str(center[1]))
    metadata.add_text("xdgame.width", str(args.width))
    metadata.add_text("xdgame.height", str(args.height))
    metadata.add_text("xdgame.time", str(time))

    try:
        Image.fromarray(np.flipud(image)).save(
            args.output,
            format="PNG",
            pnginfo=metadata,
        )
    except OSError as error:
        parser.exit(
            1,
            f"{parser.prog}: error: could not write {args.output}: {error}\n",
        )


if __name__ == "__main__":
    main()
