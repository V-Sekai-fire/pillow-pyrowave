import io
import math
from pathlib import Path

import pytest
from PIL import Image

import pillow_pyrowave

DATA = Path(__file__).parent / "data"
FRAMES = sorted(DATA.glob("*.pyrowave"))


def psnr(a: Image.Image, b: Image.Image) -> float:
    pa, pb = a.tobytes(), b.tobytes()
    mse = sum((x - y) ** 2 for x, y in zip(pa, pb)) / len(pa)
    return 99.0 if mse == 0 else 10 * math.log10(255 * 255 / mse)


def mean_rgb(im: Image.Image):
    px = im.convert("RGB").tobytes()
    n = len(px) // 3
    return tuple(sum(px[c::3]) / n for c in range(3))


def test_fixtures_present():
    assert len(FRAMES) == 4


@pytest.mark.parametrize("path", FRAMES, ids=lambda p: p.name)
def test_opens_as_pyrowave(path):
    original = Image.open(DATA / (path.name.split("_")[0] + "_" + path.name.split("_")[1] + ".png"))
    im = Image.open(path)
    assert im.format == "PYROWAVE"
    assert im.mode == "RGB"
    assert im.size == original.size
    assert pillow_pyrowave.frame_size(path.read_bytes()) == original.size


@pytest.mark.parametrize("path", FRAMES, ids=lambda p: p.name)
def test_decode_is_deterministic(path):
    a = Image.open(path).tobytes()
    b = pillow_pyrowave.decode(path.read_bytes()).tobytes()
    assert a == b


def test_more_bits_decode_closer_to_the_source():
    source = Image.open(DATA / "ramp_128x96.png").convert("RGB")
    low = psnr(Image.open(DATA / "ramp_128x96_0.5bpp.pyrowave"), source)
    high = psnr(Image.open(DATA / "ramp_128x96_4bpp.pyrowave"), source)
    assert high > low


def test_decoded_frame_is_its_own_source_not_another():
    """The ramp decode must be closer to the ramp than to a different image of the same size."""
    decoded = Image.open(DATA / "ramp_128x96_4bpp.pyrowave")
    source = Image.open(DATA / "ramp_128x96.png").convert("RGB")
    other = source.transpose(Image.Transpose.ROTATE_180)
    assert psnr(decoded, source) > psnr(decoded, other)


def test_channel_order():
    """A red source decodes red: catches Cb/Cr or R/B swapped in the conversion."""
    r, g, b = mean_rgb(Image.open(DATA / "red_64x64_4bpp.pyrowave"))
    assert r > g and r > b


def test_other_formats_are_not_taken_for_pyrowave():
    source = Image.open(DATA / "ramp_128x96.png").convert("RGB")
    for fmt in ("PNG", "JPEG", "BMP", "TIFF", "WEBP", "GIF", "PPM", "TGA", "ICO", "QOI"):
        if fmt not in Image.SAVE:
            continue
        buf = io.BytesIO()
        source.save(buf, fmt)
        data = buf.getvalue()
        assert not pillow_pyrowave._is_frame(data), fmt
        assert Image.open(io.BytesIO(data)).format == fmt


def test_truncated_frame_is_rejected():
    data = (DATA / "ramp_128x96_4bpp.pyrowave").read_bytes()
    assert pillow_pyrowave._is_frame(data)
    assert not pillow_pyrowave._is_frame(data[:-4])
    with pytest.raises(Exception):
        Image.open(io.BytesIO(data[:-4])).load()


def test_decoder_refuses_an_incomplete_frame():
    data = (DATA / "ramp_128x96_4bpp.pyrowave").read_bytes()
    first_block = 8 + (int.from_bytes(data[10:12], "little") & 0xFFF) * 4
    with pytest.raises(OSError, match="complete frame"):
        pillow_pyrowave._pyrowave.decode(data[:first_block])


def test_pq_transfer_is_refused():
    data = bytearray((DATA / "red_64x64_4bpp.pyrowave").read_bytes())
    data[7] |= 1 << (28 - 24)  # transfer_function bit of the second header word
    with pytest.raises(ValueError, match="PQ"):
        pillow_pyrowave._pyrowave.decode(bytes(data))
