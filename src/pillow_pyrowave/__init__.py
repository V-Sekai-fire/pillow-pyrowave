"""Pillow plugin for PyroWave intra frames.

``import pillow_pyrowave`` registers the format; after that ``PIL.Image.open`` reads a PyroWave
frame (one packet stream that begins with PyroWave's start-of-frame sequence header) as an RGB
image. Decoding runs on the GPU: Metal on Apple silicon, Vulkan elsewhere.
"""

from __future__ import annotations

import struct

from PIL import Image, ImageFile

from . import _pyrowave

__all__ = ["FORMAT", "PyroWaveImageFile", "frame_size", "decode"]

FORMAT = "PYROWAVE"


def _header(prefix: bytes):
    """The fields of the 8-byte sequence header, or None when the bytes do not start a frame."""
    if len(prefix) < 8:
        return None
    a, b = struct.unpack_from("<II", prefix)
    fields = {
        "width": (a & 0x3FFF) + 1,
        "height": ((a >> 14) & 0x3FFF) + 1,
        "sequence": (a >> 28) & 0x7,
        "extended": a >> 31,
        "total_blocks": b & 0xFFFFFF,
        "code": (b >> 24) & 0x3,
        "chroma_444": (b >> 26) & 0x1,
    }
    if not fields["extended"] or fields["code"] != 0 or fields["total_blocks"] == 0:
        return None
    fields["grid_blocks"] = _grid_blocks(fields["width"], fields["height"], fields["chroma_444"])
    if fields["total_blocks"] > fields["grid_blocks"]:
        return None
    return fields


# PyroWave's layout (pyrowave_common.hpp/.cpp): 5 wavelet levels, each image dimension aligned to 32
# and at least 128; level l is (aligned >> (l + 1)) wide and high and is cut into 32x32 blocks; the
# coarsest level carries 4 bands, the others 3; 4:2:0 chroma has no level-0 bands.
_LEVELS = 5


def _grid_blocks(width: int, height: int, chroma_444: int) -> int:
    def aligned(v):
        return max(-(-v // (1 << _LEVELS)) << _LEVELS, 4 << _LEVELS)

    aw, ah = aligned(width), aligned(height)
    n = 0
    for level in range(_LEVELS):
        lw, lh = aw >> (level + 1), ah >> (level + 1)
        per_band = -(-lw // 32) * -(-lh // 32)
        bands = 4 if level == _LEVELS - 1 else 3
        components = 3 if (level > 0 or chroma_444) else 1
        n += per_band * bands * components
    return n


def _block(data: bytes, offset: int, h) -> int:
    """Length in bytes of the block header at offset when it belongs to frame h, else 0."""
    if offset + 8 > len(data):
        return 0
    _ballot, bits, block = struct.unpack_from("<HHI", data, offset)
    payload_words = bits & 0xFFF  # the whole block, its own 8-byte header included, in 32-bit words
    sequence = (bits >> 12) & 0x7
    extended = bits >> 15
    block_index = block >> 8
    if extended or sequence != h["sequence"] or payload_words < 2 or block_index >= h["grid_blocks"]:
        return 0
    return payload_words * 4


def _accept(prefix: bytes) -> bool:
    """A frame opens with the sequence header and then a block header of the same frame."""
    h = _header(prefix)
    return h is not None and _block(prefix, 8, h) != 0


def _is_frame(data: bytes) -> bool:
    """Every block header belongs to the frame, the blocks end exactly at the end of the data, and
    there are as many as the sequence header counts."""
    h = _header(data)
    if h is None:
        return False
    offset, blocks = 8, 0
    while offset < len(data):
        n = _block(data, offset, h)
        if n == 0:
            return False
        offset += n
        blocks += 1
    return offset == len(data) and blocks == h["total_blocks"]


def frame_size(data: bytes) -> tuple[int, int]:
    """(width, height) from a frame's sequence header, without decoding it."""
    h = _header(data)
    if h is None:
        raise ValueError("not a PyroWave frame: no start-of-frame sequence header")
    return h["width"], h["height"]


def decode(data: bytes) -> Image.Image:
    """Decode one PyroWave frame to an RGB image."""
    width, height, rgb = _pyrowave.decode(data)
    return Image.frombytes("RGB", (width, height), rgb)


class PyroWaveImageFile(ImageFile.ImageFile):
    format = FORMAT
    format_description = "PyroWave intra frame"

    def _open(self) -> None:
        start = self.fp.tell()
        data = self.fp.read()
        if not _is_frame(data):
            raise SyntaxError("not a PyroWave frame")
        self.fp.seek(start)
        width, height = frame_size(data)
        self._mode = "RGB"
        self._size = (width, height)
        tile = ("pyrowave", (0, 0, width, height), start, None)
        self.tile = [ImageFile._Tile(*tile) if hasattr(ImageFile, "_Tile") else tile]


class PyroWaveDecoder(ImageFile.PyDecoder):
    _pulls_fd = True

    def decode(self, buffer):
        data = self.fd.read()
        width, height, rgb = _pyrowave.decode(data)
        if (width, height) != (self.state.xsize, self.state.ysize):
            raise ValueError("PyroWave frame size changed between open and decode")
        self.set_as_raw(rgb)
        return -1, 0


Image.register_open(FORMAT, PyroWaveImageFile, _accept)
Image.register_decoder("pyrowave", PyroWaveDecoder)
Image.register_extensions(FORMAT, [".pyrowave"])
Image.register_mime(FORMAT, "image/x-pyrowave")
