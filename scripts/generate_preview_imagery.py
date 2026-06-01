#!/usr/bin/env python3
"""Generate deterministic fictional satellite-style preview PNGs."""

from __future__ import annotations

import json
import math
import random
import struct
import zlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCATIONS_PATH = REPO_ROOT / "site" / "src" / "lib" / "data" / "locations.json"
OUTPUT_DIR = REPO_ROOT / "site" / "static" / "assets" / "locations"
WIDTH = 640
HEIGHT = 360


PALETTES = {
    "Transport": [(190, 184, 142), (83, 92, 73), (219, 212, 175), (126, 117, 88)],
    "Science": [(213, 206, 177), (238, 232, 200), (116, 137, 145), (91, 106, 96)],
    "Entertainment": [(92, 124, 89), (194, 170, 116), (68, 82, 67), (220, 202, 152)],
    "Land Art": [(95, 138, 87), (178, 188, 105), (79, 113, 91), (214, 204, 139)],
    "Waterworks": [(52, 92, 104), (157, 151, 124), (34, 67, 82), (204, 195, 158)],
    "Structures": [(172, 162, 133), (218, 210, 183), (112, 102, 88), (81, 118, 105)],
    "Infrastructure": [(153, 77, 58), (198, 135, 92), (69, 74, 70), (219, 191, 145)],
    "Maritime": [(31, 88, 111), (58, 133, 151), (186, 178, 145), (222, 213, 176)],
    "Ancient Forms": [(180, 139, 72), (216, 185, 116), (98, 86, 68), (231, 210, 154)],
    "Sports": [(61, 109, 69), (151, 173, 103), (213, 199, 151), (74, 82, 77)],
    "Agriculture": [(126, 155, 86), (190, 180, 98), (76, 110, 70), (210, 198, 140)],
}


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, pixels: list[list[tuple[int, int, int]]]) -> None:
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for red, green, blue in row:
            raw.extend((red, green, blue))
    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
    data += png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += png_chunk(b"IEND", b"")
    path.write_bytes(data)


def blend(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(a[i] * (1 - amount) + b[i] * amount))) for i in range(3))


def draw_rect(pixels, x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(HEIGHT, y1)):
        row = pixels[y]
        for x in range(max(0, x0), min(WIDTH, x1)):
            row[x] = color


def draw_line(pixels, x0, y0, x1, y1, color, width=3):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for step in range(steps + 1):
        x = round(x0 + (x1 - x0) * step / steps)
        y = round(y0 + (y1 - y0) * step / steps)
        draw_rect(pixels, x - width, y - width, x + width + 1, y + width + 1, color)


def draw_ellipse(pixels, cx, cy, rx, ry, color, ring=False):
    for y in range(max(0, cy - ry), min(HEIGHT, cy + ry + 1)):
        for x in range(max(0, cx - rx), min(WIDTH, cx + rx + 1)):
            value = ((x - cx) / max(rx, 1)) ** 2 + ((y - cy) / max(ry, 1)) ** 2
            if (0.72 < value < 1.08) if ring else value <= 1:
                pixels[y][x] = color


def base_pixels(seed: int, palette):
    rng = random.Random(seed)
    ground = palette[0]
    pixels = []
    for y in range(HEIGHT):
        row = []
        for x in range(WIDTH):
            wave = math.sin((x + seed % 100) / 43) + math.cos((y - seed % 80) / 37)
            noise = rng.randint(-9, 9)
            color = blend(ground, palette[1], 0.08 + wave * 0.018)
            row.append(tuple(max(0, min(255, channel + noise)) for channel in color))
        pixels.append(row)
    return pixels


def draw_scene(location: dict[str, object]) -> list[list[tuple[int, int, int]]]:
    slug = str(location["slug"])
    seed = sum((index + 1) * ord(char) for index, char in enumerate(slug))
    rng = random.Random(seed)
    palette = PALETTES.get(str(location["category"]), PALETTES["Structures"])
    pixels = base_pixels(seed, palette)

    for _ in range(12):
        x = rng.randrange(0, WIDTH - 80)
        y = rng.randrange(0, HEIGHT - 50)
        draw_rect(pixels, x, y, x + rng.randrange(30, 95), y + rng.randrange(18, 60), blend(palette[0], palette[2], 0.35))

    for _ in range(5):
        draw_line(
            pixels,
            rng.randrange(-40, WIDTH),
            rng.randrange(0, HEIGHT),
            rng.randrange(0, WIDTH + 40),
            rng.randrange(0, HEIGHT),
            blend(palette[2], (245, 240, 211), 0.35),
            rng.randrange(2, 5),
        )

    category = str(location["category"])
    if category in {"Transport", "Sports", "Entertainment"}:
        draw_ellipse(pixels, WIDTH // 2, HEIGHT // 2, 130, 75, blend(palette[3], (255, 255, 255), 0.12), ring=True)
        draw_ellipse(pixels, WIDTH // 2, HEIGHT // 2, 65, 38, blend(palette[0], palette[1], 0.28))
    elif category in {"Waterworks", "Maritime"}:
        draw_rect(pixels, 0, HEIGHT // 2 - 35, WIDTH, HEIGHT // 2 + 42, palette[2])
        for offset in range(60, WIDTH, 95):
            draw_rect(pixels, offset, HEIGHT // 2 - 55, offset + 52, HEIGHT // 2 + 58, blend(palette[1], palette[3], 0.25))
    elif category == "Agriculture":
        for radius in range(22, 148, 18):
            draw_ellipse(pixels, WIDTH // 2, HEIGHT // 2, radius * 2, radius, blend(palette[1], palette[2], 0.35), ring=True)
    elif category == "Ancient Forms":
        for inset in range(0, 95, 18):
            draw_rect(pixels, WIDTH // 2 - 115 + inset, HEIGHT // 2 - 80 + inset, WIDTH // 2 + 115 - inset, HEIGHT // 2 + 80 - inset, blend(palette[1], palette[3], inset / 130))
    else:
        for _ in range(9):
            draw_ellipse(pixels, rng.randrange(100, WIDTH - 100), rng.randrange(70, HEIGHT - 70), rng.randrange(18, 42), rng.randrange(18, 42), palette[3])

    return pixels


def main() -> int:
    locations = json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    provenance = []
    for location in locations:
        slug = str(location["slug"])
        image_path = OUTPUT_DIR / f"{slug}.png"
        write_png(image_path, draw_scene(location))
        provenance.append(
            {
                "slug": slug,
                "status": "fictional-generated",
                "method": "deterministic procedural preview imagery; replace with AI image batch when OPENAI_API_KEY is available",
                "generatedAt": "2026-06-01",
                "source": "No real-world map tiles or satellite imagery used",
            }
        )
    (OUTPUT_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
