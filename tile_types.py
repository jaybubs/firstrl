from typing import Tuple

import numpy as np  # type: ignore

# tile grahpics structured type compatible with Console.tiles_rgb
graphic_dt = np.dtype(
    [
        ("ch", np.int32),  # unicode codepoint, character in integer format
        ("fg", "3B"),  # 3 unsigned bytes for RGB foreground
        ("bg", "3B"),  # same but background
    ]
)

tile_dt = np.dtype(
    [
        ("walkable", np.bool),  # true if can be walked over
        ("transparent", np.bool),  # true if doesn't block fov
        ("dark", graphic_dt),  # tile not in fov
        ("light", graphic_dt),  # when the tile is in FOV
    ]
)


def new_tile(
    *,  # enforce the use of keywords so parameter order doesn't matter
    walkable: int,
    transparent: int,
    dark: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    light: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
) -> np.ndarray:
    """helper fx for definining individiual tile types"""
    return np.array((walkable, transparent, dark, light), dtype=tile_dt)


# represents unseen tiles
SHROUD = np.array((ord(" "), (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)

floor = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord(" "), (255, 255, 255), (50, 50, 150)),
    light=(ord(" "), (255, 255, 255), (200, 180, 50)),
)

wall = new_tile(
    walkable=False,
    transparent=False,
    dark=(ord(" "), (255, 255, 255), (0, 0, 100)),
    light=(ord(" "), (255, 255, 255), (130, 110, 50)),
)
