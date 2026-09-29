import argparse
from collections import deque
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pygame
from numpy.typing import NDArray

from ._runtime import Action, Game, config_from_toml

_PLASMA = np.array(
    [
        [12, 7, 134],
        [16, 7, 135],
        [19, 6, 137],
        [21, 6, 138],
        [24, 6, 139],
        [27, 6, 140],
        [29, 6, 141],
        [31, 5, 142],
        [33, 5, 143],
        [35, 5, 144],
        [37, 5, 145],
        [39, 5, 146],
        [41, 5, 147],
        [43, 5, 148],
        [45, 4, 148],
        [47, 4, 149],
        [49, 4, 150],
        [51, 4, 151],
        [52, 4, 152],
        [54, 4, 152],
        [56, 4, 153],
        [58, 4, 154],
        [59, 3, 154],
        [61, 3, 155],
        [63, 3, 156],
        [64, 3, 156],
        [66, 3, 157],
        [68, 3, 158],
        [69, 3, 158],
        [71, 2, 159],
        [73, 2, 159],
        [74, 2, 160],
        [76, 2, 161],
        [78, 2, 161],
        [79, 2, 162],
        [81, 1, 162],
        [82, 1, 163],
        [84, 1, 163],
        [86, 1, 163],
        [87, 1, 164],
        [89, 1, 164],
        [90, 0, 165],
        [92, 0, 165],
        [94, 0, 165],
        [95, 0, 166],
        [97, 0, 166],
        [98, 0, 166],
        [100, 0, 167],
        [101, 0, 167],
        [103, 0, 167],
        [104, 0, 167],
        [106, 0, 167],
        [108, 0, 168],
        [109, 0, 168],
        [111, 0, 168],
        [112, 0, 168],
        [114, 0, 168],
        [115, 0, 168],
        [117, 0, 168],
        [118, 1, 168],
        [120, 1, 168],
        [121, 1, 168],
        [123, 2, 168],
        [124, 2, 167],
        [126, 3, 167],
        [127, 3, 167],
        [129, 4, 167],
        [130, 4, 167],
        [132, 5, 166],
        [133, 6, 166],
        [134, 7, 166],
        [136, 7, 165],
        [137, 8, 165],
        [139, 9, 164],
        [140, 10, 164],
        [142, 12, 164],
        [143, 13, 163],
        [144, 14, 163],
        [146, 15, 162],
        [147, 16, 161],
        [149, 17, 161],
        [150, 18, 160],
        [151, 19, 160],
        [153, 20, 159],
        [154, 21, 158],
        [155, 23, 158],
        [157, 24, 157],
        [158, 25, 156],
        [159, 26, 155],
        [160, 27, 155],
        [162, 28, 154],
        [163, 29, 153],
        [164, 30, 152],
        [165, 31, 151],
        [167, 33, 151],
        [168, 34, 150],
        [169, 35, 149],
        [170, 36, 148],
        [172, 37, 147],
        [173, 38, 146],
        [174, 39, 145],
        [175, 40, 144],
        [176, 42, 143],
        [177, 43, 143],
        [178, 44, 142],
        [180, 45, 141],
        [181, 46, 140],
        [182, 47, 139],
        [183, 48, 138],
        [184, 50, 137],
        [185, 51, 136],
        [186, 52, 135],
        [187, 53, 134],
        [188, 54, 133],
        [189, 55, 132],
        [190, 56, 131],
        [191, 57, 130],
        [192, 59, 129],
        [193, 60, 128],
        [194, 61, 128],
        [195, 62, 127],
        [196, 63, 126],
        [197, 64, 125],
        [198, 65, 124],
        [199, 66, 123],
        [200, 68, 122],
        [201, 69, 121],
        [202, 70, 120],
        [203, 71, 119],
        [204, 72, 118],
        [205, 73, 117],
        [206, 74, 117],
        [207, 75, 116],
        [208, 77, 115],
        [209, 78, 114],
        [209, 79, 113],
        [210, 80, 112],
        [211, 81, 111],
        [212, 82, 110],
        [213, 83, 109],
        [214, 85, 109],
        [215, 86, 108],
        [215, 87, 107],
        [216, 88, 106],
        [217, 89, 105],
        [218, 90, 104],
        [219, 91, 103],
        [220, 93, 102],
        [220, 94, 102],
        [221, 95, 101],
        [222, 96, 100],
        [223, 97, 99],
        [223, 98, 98],
        [224, 100, 97],
        [225, 101, 96],
        [226, 102, 96],
        [227, 103, 95],
        [227, 104, 94],
        [228, 106, 93],
        [229, 107, 92],
        [229, 108, 91],
        [230, 109, 90],
        [231, 110, 90],
        [232, 112, 89],
        [232, 113, 88],
        [233, 114, 87],
        [234, 115, 86],
        [234, 116, 85],
        [235, 118, 84],
        [236, 119, 84],
        [236, 120, 83],
        [237, 121, 82],
        [237, 123, 81],
        [238, 124, 80],
        [239, 125, 79],
        [239, 126, 78],
        [240, 128, 77],
        [240, 129, 77],
        [241, 130, 76],
        [242, 132, 75],
        [242, 133, 74],
        [243, 134, 73],
        [243, 135, 72],
        [244, 137, 71],
        [244, 138, 71],
        [245, 139, 70],
        [245, 141, 69],
        [246, 142, 68],
        [246, 143, 67],
        [246, 145, 66],
        [247, 146, 65],
        [247, 147, 65],
        [248, 149, 64],
        [248, 150, 63],
        [248, 152, 62],
        [249, 153, 61],
        [249, 154, 60],
        [250, 156, 59],
        [250, 157, 58],
        [250, 159, 58],
        [250, 160, 57],
        [251, 162, 56],
        [251, 163, 55],
        [251, 164, 54],
        [252, 166, 53],
        [252, 167, 53],
        [252, 169, 52],
        [252, 170, 51],
        [252, 172, 50],
        [252, 173, 49],
        [253, 175, 49],
        [253, 176, 48],
        [253, 178, 47],
        [253, 179, 46],
        [253, 181, 45],
        [253, 182, 45],
        [253, 184, 44],
        [253, 185, 43],
        [253, 187, 43],
        [253, 188, 42],
        [253, 190, 41],
        [253, 192, 41],
        [253, 193, 40],
        [253, 195, 40],
        [253, 196, 39],
        [253, 198, 38],
        [252, 199, 38],
        [252, 201, 38],
        [252, 203, 37],
        [252, 204, 37],
        [252, 206, 37],
        [251, 208, 36],
        [251, 209, 36],
        [251, 211, 36],
        [250, 213, 36],
        [250, 214, 36],
        [250, 216, 36],
        [249, 217, 36],
        [249, 219, 36],
        [248, 221, 36],
        [248, 223, 36],
        [247, 224, 36],
        [247, 226, 37],
        [246, 228, 37],
        [246, 229, 37],
        [245, 231, 38],
        [245, 233, 38],
        [244, 234, 38],
        [243, 236, 38],
        [243, 238, 38],
        [242, 240, 38],
        [242, 241, 38],
        [241, 243, 38],
        [240, 245, 37],
        [240, 246, 35],
        [239, 248, 33],
    ],
    dtype=np.uint8,
)


def _plasma_rgb(value: int) -> tuple[int, int, int]:
    color = _PLASMA[value]
    return int(color[0]), int(color[1]), int(color[2])


_UINT32_MAX = (1 << 32) - 1
_FAST_MODE_DELAY_MS = 500
_FAST_MODE_INTERVAL_MS = 100
_HISTORY_LENGTH = 100
_HISTORY_VALUE_WIDTH = 80
_HISTORY_POINT_RADIUS = 4

_VIEW_SIZE = 460
_PANEL_WIDTH = 280
_MARGIN = 20
_WINDOW_SIZE = _VIEW_SIZE + _PANEL_WIDTH + 3 * _MARGIN, _VIEW_SIZE + 2 * _MARGIN

_BACKGROUND = "#181818"
_PANEL_BACKGROUND = "#242424"
_PLOT_BACKGROUND = "#1d1d1d"
_PLOT_BORDER = "#444444"
_TEXT = "#eeeeee"
_MUTED_TEXT = "#aaaaaa"
_INACTIVE_COLOR = "#444444"
_REWARD_COLOR = "#ffca28"
_SATIETY_COLOR = "#66bb6a"
_HYDRATION_COLOR = "#42a5f5"
_BEAN_BORDER_COLOR = "#00e5ff"
_AGENT_BORDER_COLOR = "#39ff14"
_CELL_BORDER_WIDTH = 2

_KEY_ACTIONS = {
    pygame.K_w: Action.MOVE_NORTH,
    pygame.K_UP: Action.MOVE_NORTH,
    pygame.K_a: Action.MOVE_WEST,
    pygame.K_LEFT: Action.MOVE_WEST,
    pygame.K_s: Action.MOVE_SOUTH,
    pygame.K_DOWN: Action.MOVE_SOUTH,
    pygame.K_d: Action.MOVE_EAST,
    pygame.K_RIGHT: Action.MOVE_EAST,
    pygame.K_e: Action.EAT_BEAN,
    pygame.K_f: Action.PICKUP_BEAN,
    pygame.K_r: Action.DROP_BEAN,
    pygame.K_SPACE: Action.NOP,
}

_REPEATABLE_KEYS = frozenset(
    {
        pygame.K_w,
        pygame.K_UP,
        pygame.K_a,
        pygame.K_LEFT,
        pygame.K_s,
        pygame.K_DOWN,
        pygame.K_d,
        pygame.K_RIGHT,
        pygame.K_SPACE,
    }
)

_ACTION_LABELS = (
    ("W / Up", "Move north"),
    ("A / Left", "Move west"),
    ("S / Down", "Move south"),
    ("D / Right", "Move east"),
    ("E", "Eat bean"),
    ("F", "Pick up bean"),
    ("R", "Drop bean"),
    ("Space", "Wait"),
    ("Q / Esc", "Quit"),
)


def _draw_history(
    screen: pygame.Surface,
    font: pygame.font.Font,
    label: str,
    history: deque[float],
    current_value: str,
    color: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    screen.blit(font.render(label, True, _TEXT), (x, y))

    plot_top = y + font.get_linesize()
    plot_bottom = y + height
    plot_right = x + width - _HISTORY_VALUE_WIDTH
    plot_rect = pygame.Rect(x, plot_top, plot_right - x, plot_bottom - plot_top)

    pygame.draw.rect(screen, _PLOT_BACKGROUND, plot_rect)
    pygame.draw.rect(screen, _PLOT_BORDER, plot_rect, 1)

    minimum = min(history)
    maximum = max(history)
    if minimum == maximum:
        minimum -= 1.0
        maximum += 1.0

    vertical_range = maximum - minimum
    usable_height = plot_bottom - plot_top - 2 * _HISTORY_POINT_RADIUS
    plot_start = x + _HISTORY_POINT_RADIUS
    plot_end = plot_right - _HISTORY_POINT_RADIUS
    x_step = (plot_end - plot_start) / (_HISTORY_LENGTH - 1)

    points = []
    for index, value in enumerate(history):
        point_x = plot_end - (len(history) - 1 - index) * x_step
        fraction = (value - minimum) / vertical_range
        point_y = plot_bottom - _HISTORY_POINT_RADIUS - fraction * usable_height
        points.append((round(point_x), round(point_y)))

    if len(points) > 1:
        pygame.draw.aalines(screen, color, False, points)

    current_point = points[-1]
    pygame.draw.circle(screen, color, current_point, _HISTORY_POINT_RADIUS)

    value_surface = font.render(current_value, True, _TEXT)
    value_y = min(
        max(current_point[1] - value_surface.get_height() // 2, plot_top),
        plot_bottom - value_surface.get_height(),
    )
    screen.blit(value_surface, (plot_right + 8, value_y))


def _draw_fov(screen: pygame.Surface, channels: NDArray[np.uint8]) -> None:
    fov = np.flipud(channels)
    height, width, _ = fov.shape
    center_x = width // 2
    center_y = height // 2
    borders: list[tuple[pygame.Rect, str]] = []

    for y in range(height):
        top = _MARGIN + y * _VIEW_SIZE // height
        bottom = _MARGIN + (y + 1) * _VIEW_SIZE // height
        for x in range(width):
            left = _MARGIN + x * _VIEW_SIZE // width
            right = _MARGIN + (x + 1) * _VIEW_SIZE // width
            rect = pygame.Rect(left, top, right - left, bottom - top)

            red, green, illumination = map(int, fov[y, x])
            has_bean = red != 0 or green != 0
            if not has_bean:
                pygame.draw.rect(
                    screen,
                    (illumination, illumination, illumination),
                    rect,
                )
            else:
                pygame.draw.rect(
                    screen,
                    _plasma_rgb(red),
                    rect,
                )
                pygame.draw.polygon(
                    screen,
                    _plasma_rgb(green),
                    (rect.topright, rect.bottomright, rect.bottomleft),
                )

            is_agent = x == center_x and y == center_y
            if is_agent or has_bean:
                border_color = _AGENT_BORDER_COLOR if is_agent else _BEAN_BORDER_COLOR
                borders.append((rect, border_color))

    for rect, color in borders:
        pygame.draw.rect(
            screen,
            color,
            rect,
            _CELL_BORDER_WIDTH,
        )


def _draw(
    screen: pygame.Surface,
    game: Game,
    font: pygame.font.Font,
    heading_font: pygame.font.Font,
    reward_history: deque[float],
    satiety_history: deque[float],
    hydration_history: deque[float],
) -> None:
    screen.fill(_BACKGROUND)

    _draw_fov(screen, game.fov)

    panel_x = _VIEW_SIZE + 2 * _MARGIN
    pygame.draw.rect(
        screen,
        _PANEL_BACKGROUND,
        (panel_x, _MARGIN, _PANEL_WIDTH, _VIEW_SIZE),
    )
    content_x = panel_x + _MARGIN
    content_width = _PANEL_WIDTH - 2 * _MARGIN

    screen.blit(heading_font.render("Status", True, _TEXT), (content_x, 35))

    _draw_history(
        screen,
        font,
        "Reward",
        reward_history,
        f"{reward_history[-1]:,.2f}",
        _REWARD_COLOR,
        content_x,
        65,
        content_width,
        52,
    )
    _draw_history(
        screen,
        font,
        "Satiety",
        satiety_history,
        f"{satiety_history[-1]:+.1f}",
        _SATIETY_COLOR,
        content_x,
        120,
        content_width,
        52,
    )
    _draw_history(
        screen,
        font,
        "Hydration",
        hydration_history,
        f"{hydration_history[-1]:+.1f}",
        _HYDRATION_COLOR,
        content_x,
        175,
        content_width,
        52,
    )

    inventory_y = 242
    inventory_color = _SATIETY_COLOR if game.inventory_count else _INACTIVE_COLOR
    pygame.draw.circle(screen, inventory_color, (content_x + 8, inventory_y + 9), 8)
    inventory = "Bean carried" if game.inventory_count else "Inventory empty"
    screen.blit(font.render(inventory, True, _TEXT), (content_x + 25, inventory_y))

    screen.blit(heading_font.render("Actions", True, _TEXT), (content_x, 277))

    for row, (key, action) in enumerate(_ACTION_LABELS):
        y = 311 + row * 18
        screen.blit(font.render(key, True, _TEXT), (content_x, y))
        screen.blit(font.render(action, True, _MUTED_TEXT), (content_x + 105, y))

    pygame.display.flip()


def _run(game: Game, seed: int) -> None:
    screen = pygame.display.set_mode(_WINDOW_SIZE)
    font = pygame.font.Font(None, 21)
    heading_font = pygame.font.Font(None, 27)

    tick = 0
    cumulative_reward = 0.0
    reward_history = deque([cumulative_reward], maxlen=_HISTORY_LENGTH)
    satiety_history = deque([game.satiety_level], maxlen=_HISTORY_LENGTH)
    hydration_history = deque([game.hydration_level], maxlen=_HISTORY_LENGTH)

    pygame.key.set_repeat(_FAST_MODE_DELAY_MS, _FAST_MODE_INTERVAL_MS)

    pygame.display.set_caption(f"10d-game — seed={seed}, tick={tick}")

    _draw(
        screen,
        game,
        font,
        heading_font,
        reward_history,
        satiety_history,
        hydration_history,
    )

    running = True
    while running:
        event = pygame.event.wait(100)

        if event.type == pygame.QUIT or (
            event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q)
        ):
            running = False

        elif (
            event.type == pygame.KEYDOWN
            and event.key in _KEY_ACTIONS
            and (not getattr(event, "repeat", False) or event.key in _REPEATABLE_KEYS)
        ):
            cumulative_reward += game.tick(_KEY_ACTIONS[event.key])
            reward_history.append(cumulative_reward)
            satiety_history.append(game.satiety_level)
            hydration_history.append(game.hydration_level)
            tick += 1
            pygame.display.set_caption(f"10d-game — t={tick}, seed={seed}")
            _draw(
                screen,
                game,
                font,
                heading_font,
                reward_history,
                satiety_history,
                hydration_history,
            )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="xdgame-play",
        description="Control a 10d-game agent in a simple graphical interface.",
    )
    parser.add_argument("wasm", type=Path, help="path to 10d_game.wasm")
    parser.add_argument("--seed", required=True, type=int, help="world seed")
    parser.add_argument(
        "--config",
        type=Path,
        help="TOML configuration file (default: game-engine defaults)",
    )
    args = parser.parse_args(argv)

    if not args.wasm.is_file():
        parser.error(f"WASM file does not exist: {args.wasm}")

    if args.config is not None and not args.config.is_file():
        parser.error(f"configuration file does not exist: {args.config}")

    if not 0 <= args.seed <= _UINT32_MAX:
        parser.error("--seed must fit in uint32_t")

    if args.config is None:
        config = None
    else:
        try:
            config = config_from_toml(args.config, wasm=args.wasm)
        except (OSError, TypeError, ValueError) as error:
            parser.error(f"invalid --config: {error}")

    pygame.init()

    try:
        with Game(args.wasm, args.seed, config) as game:
            _run(game, args.seed)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
