# pillow-pyrowave

A [Pillow](https://python-pillow.org/) plugin that reads [PyroWave](https://github.com/Themaister/pyrowave)
intra frames. After `import pillow_pyrowave`, `PIL.Image.open` opens a PyroWave frame as an RGB image.
Decoding runs on the GPU: PyroWave's Metal port on Apple silicon, its Vulkan library on Linux and
Windows.

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

`pillow_pyrowave.frame_size(data)` reads the width and height from a frame's header without decoding.

## What it reads

One PyroWave frame: the 8-byte start-of-frame sequence header, then the frame's blocks. This is what
PyroWave's encoder emits for one image, and what the `cua-tracer` and XR Pilot trace stores keep for
each window view. A file is taken as PyroWave only when its whole structure checks out: every block
header belongs to the frame, every block index lies inside the frame's block grid, and the blocks end
exactly at the end of the data, as many as the header counts.

Output is 8-bit sRGB RGB. Frames with BT.709 primaries, transfer and YCbCr transform, full or limited
range, 4:2:0 or 4:4:4 chroma, are converted. Frames with BT.2020 primaries or transform, or the PQ
transfer, are refused with a `ValueError` rather than converted to the wrong colours. Full-range chroma
is read as `byte / 255 - 0.5`, the inverse of the `cua-tracer-pyrowave` and XR Pilot encoders.

Reading only. There is no `save` support.

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
independent encoder, made from them (`tools/make_fixtures.py`).

## Licence

MIT. PyroWave is MIT, copyright Hans-Kristian Arntzen.
