#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of ksooo's Kodi add-on repository
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Generate the repository add-on icon.

The icon shows three stacked plates - a collection of add-ons - with the
topmost one in the accent colour. Everything is drawn from primitives, so no
third party imaging library is needed.

Usage: python3 tools/make_icon.py [output.png]
"""

import os
import sys

import pngwriter

SIZE = 512

BACKGROUND_TOP = (0x1B, 0x27, 0x33)
BACKGROUND_BOTTOM = (0x0E, 0x16, 0x20)

#: Top to bottom: the plate nearest the viewer carries the accent colour, the
#: ones behind it recede into the background.
PLATE_COLOURS = ((0x11, 0xE5, 0xFF), (0xEE, 0xF4, 0xF9), (0x8F, 0xA3, 0xB4))
PLATE_TOPS = (118.0, 219.0, 320.0)
PLATE_LEFT, PLATE_RIGHT = 96.0, 416.0
PLATE_HEIGHT = 74.0
PLATE_RADIUS = 18.0


def in_rounded_rect(x, y, left, top, right, bottom, radius):
    """Return whether the given point lies inside the given rounded rectangle."""
    if x < left or x > right or y < top or y > bottom:
        return False

    # Clamping into the corner circle centres turns the corner test into a
    # plain distance test and leaves the straight edges at distance zero.
    centre_x = min(max(x, left + radius), right - radius)
    centre_y = min(max(y, top + radius), bottom - radius)
    return (x - centre_x) ** 2 + (y - centre_y) ** 2 <= radius * radius


def background_colour(y):
    """Return the vertical gradient colour at the given height."""
    ratio = y / SIZE
    return tuple(int(round(top + (bottom - top) * ratio))
                 for top, bottom in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM))


def sample(x, y):
    """Return the RGBA colour of the icon at the given point."""
    for top, colour in zip(PLATE_TOPS, PLATE_COLOURS):
        if in_rounded_rect(x, y, PLATE_LEFT, top, PLATE_RIGHT, top + PLATE_HEIGHT, PLATE_RADIUS):
            return colour + (255,)
    return background_colour(y) + (255,)


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, 'src', 'repository.kodi.ksooo', 'icon.png')

    pngwriter.write_png(path, SIZE, SIZE, pngwriter.render(SIZE, SIZE, sample))
    print('wrote {}'.format(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
