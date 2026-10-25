"""Regenerate the test fixtures: generated RGB images and their PyroWave frames.

The frames come from cua-tracer-pyrowave (V-Sekai-fire/interactor-cua-driver, rust/pyrowave-sidecar),
an independent PyroWave encoder, so the tests check this package against frames it did not make.

    python tools/make_fixtures.py <path to cua-tracer-pyrowave>
"""

import math
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "tests" / "data"


def ramp(w, h):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (x * 255 // (w - 1), y * 255 // (h - 1),
                        int(128 + 127 * math.sin(x / 7.0) * math.cos(y / 5.0)))
    return im


def flat(w, h, colour):
    return Image.new("RGB", (w, h), colour)


def encode(sidecar, im, bpp):
    w, h = im.size
    rgba = im.convert("RGBA").tobytes()
    budget = int(w * h * bpp / 8)
    p = subprocess.run([sidecar], input=struct.pack("<III", w, h, budget) + rgba,
                       stdout=subprocess.PIPE, check=True)
    (n,) = struct.unpack_from("<I", p.stdout)
    if n == 0:
        raise SystemExit(f"{w}x{h} at {bpp} bpp: the sidecar could not encode")
    return p.stdout[4:4 + n]


def main(sidecar):
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {"ramp_128x96": ramp(128, 96), "red_64x64": flat(64, 64, (220, 30, 30))}
    for name, im in cases.items():
        im.save(OUT / f"{name}.png")
        for bpp in (0.5, 4.0):
            (OUT / f"{name}_{bpp:g}bpp.pyrowave").write_bytes(encode(sidecar, im, bpp))
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size)


if __name__ == "__main__":
    main(sys.argv[1])
