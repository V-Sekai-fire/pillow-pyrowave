# pillow-pyrowave

**Open a PyroWave frame with `Image.open`.**

[PyroWave](https://github.com/Themaister/pyrowave) frames are GPU wavelet packets, and Pillow cannot
read them. Without a decoder, every frame in a trace store stays a blob of bytes.

This [Pillow](https://python-pillow.org/) plugin decodes each frame on the GPU (PyroWave's Metal port on
Apple silicon, its Vulkan library on Linux and Windows) and gives back an RGB image.

```bash
pip install git+https://github.com/V-Sekai-fire/pillow-pyrowave
```

```python
import io
from PIL import Image
import pillow_pyrowave  # registers the format

im = Image.open(io.BytesIO(frame_bytes))   # im.format == "PYROWAVE", im.mode == "RGB"
im.save("frame.png")
```

Try it on a window view from a `cua-tracer` or XR Pilot trace store. To get the size without decoding,
call `pillow_pyrowave.frame_size(data)`.

## What it reads

**One frame, checked end to end.** A file is taken as PyroWave only when its whole structure checks
out, so other images are never mistaken for it.

A frame is what PyroWave's encoder emits for one image: the 8-byte start-of-frame sequence header,
then the frame's blocks. Every block header must belong to the frame, every block index must lie
inside the frame's block grid, and the blocks must end exactly at the end of the data, as many as the
header counts.

Output is 8-bit sRGB RGB:

| Frame | Result |
|---|---|
| BT.709 primaries, transfer and YCbCr transform; full or limited range; 4:2:0 or 4:4:4 chroma | converted |
| BT.2020 primaries or transform, or the PQ transfer | refused with a `ValueError`, not converted to the wrong colours |

Full-range chroma is read as `byte / 255 - 0.5`, the inverse of the `cua-tracer-pyrowave` and XR Pilot
encoders. The plugin reads only: there is no `save` support.

## Requirements

- macOS on Apple silicon (Apple7 GPU family or newer), or Linux or Windows with a Vulkan driver whose
  device has 8-bit storage and clustered subgroup operations.
- A C++17 compiler and CMake 3.20 or newer to build from source. The build fetches PyroWave
  (V-Sekai-fire/pyrowave, pinned) and, off Apple, a pinned Granite subset; no Vulkan SDK is needed.

## Tests

```bash
pip install ".[test]" && pytest
```

The fixtures in `tests/data` are generated images and the frames that `cua-tracer-pyrowave`, an
independent encoder, made from them (`tools/make_fixtures.py`). Run that script to make them again.

## Licence

MIT. PyroWave is MIT, copyright Hans-Kristian Arntzen.
