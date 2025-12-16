#!/usr/bin/env python3
import os
import struct
import zlib


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def write_png_rgb(path: str, width: int, height: int, pixel_fn) -> None:
    rows = []
    for y in range(height):
        row = bytearray([0])  # filter type 0
        for x in range(width):
            r, g, b = pixel_fn(x, y)
            row += bytes((r & 255, g & 255, b & 255))
        rows.append(bytes(row))

    raw = b"".join(rows)
    compressed = zlib.compress(raw, level=9)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit truecolor
    png = signature + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def ogp_pixel(x: int, y: int) -> tuple[int, int, int]:
    base = (15, 23, 42)
    if 80 < (x - y // 2) % 1200 < 520 and 180 < y < 450:
        return (44, 116, 179)

    dx = abs(x - 600) / 600
    dy = abs(y - 315) / 315
    vignette = 1 - 0.25 * (dx * dx + dy * dy)
    return tuple(max(0, min(255, int(c * vignette))) for c in base)


def favicon_pixel(x: int, y: int) -> tuple[int, int, int]:
    if x < 128 and y < 128:
        return (44, 116, 179)
    if x >= 128 and y < 128:
        return (15, 23, 42)
    if x < 128 and y >= 128:
        return (15, 23, 42)
    return (44, 116, 179)


def main() -> int:
    outputs = [
        ("frontend/public/ogp.png", 1200, 630, ogp_pixel),
        ("frontend/public/favicon.png", 256, 256, favicon_pixel),
        ("frontend/dist/ogp.png", 1200, 630, ogp_pixel),
        ("frontend/dist/favicon.png", 256, 256, favicon_pixel),
    ]

    for path, w, h, fn in outputs:
        write_png_rgb(path, w, h, fn)
        print(f"wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

