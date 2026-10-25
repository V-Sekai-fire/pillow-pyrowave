#include "decode.hpp"
#include <algorithm>
#include <cmath>

namespace pyrowave_pil
{
namespace
{
uint32_t word(const uint8_t* p)
{
    return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}
uint8_t unit(float v)
{
    return uint8_t(std::lround(std::clamp(v, 0.0f, 1.0f) * 255.0f));
}
} // namespace

bool parseHeader(const uint8_t* data, size_t size, Header& out)
{
    if (size < 8)
        return false;
    const uint32_t a = word(data), b = word(data + 4);
    out.width = int(a & 0x3fffu) + 1;
    out.height = int((a >> 14) & 0x3fffu) + 1;
    out.extended = (a >> 31) != 0;
    out.total_blocks = b & 0xffffffu;
    out.code = int((b >> 24) & 0x3u);
    out.chroma_444 = ((b >> 26) & 1u) != 0;
    out.color_primaries = int((b >> 27) & 1u);
    out.transfer_function = int((b >> 28) & 1u);
    out.ycbcr_transform = int((b >> 29) & 1u);
    out.limited_range = ((b >> 30) & 1u) != 0;
    out.chroma_siting = int((b >> 31) & 1u);
    return out.extended && out.code == 0 && out.total_blocks != 0;
}

std::string unsupported(const Header& h)
{
    if (h.color_primaries != 0)
        return "BT.2020 primaries; this package returns sRGB (BT.709) RGB only";
    if (h.transfer_function != 0)
        return "PQ transfer; this package returns 8-bit SDR RGB only";
    if (h.ycbcr_transform != 0)
        return "BT.2020 YCbCr transform";
    if (!h.chroma_444 && (h.width % 2 || h.height % 2))
        return "odd extent with 4:2:0 chroma";
    return {};
}

Planes sized(const Header& h)
{
    Planes p;
    p.width = h.width;
    p.height = h.height;
    p.chroma_444 = h.chroma_444;
    p.y.resize(size_t(p.width) * size_t(p.height));
    p.cb.resize(size_t(p.chromaWidth()) * size_t(p.chromaHeight()));
    p.cr.resize(p.cb.size());
    return p;
}

std::vector<uint8_t> toRgb(const Planes& p, bool limited_range)
{
    // BT.709: Kr 0.2126, Kb 0.0722 (ITU-R BT.709-6, table 3).
    const float yScale = limited_range ? 255.0f / 219.0f : 1.0f;
    const float yOffset = limited_range ? 16.0f : 0.0f;
    const float cScale = limited_range ? 255.0f / 224.0f : 1.0f;
    const int shift = p.chroma_444 ? 0 : 1;
    std::vector<uint8_t> rgb(size_t(p.width) * size_t(p.height) * 3);
    for (int y = 0; y < p.height; ++y)
        for (int x = 0; x < p.width; ++x)
        {
            const size_t c = size_t(y >> shift) * size_t(p.chromaWidth()) + size_t(x >> shift);
            const float Y = (p.y[size_t(y) * size_t(p.width) + size_t(x)] - yOffset) * yScale / 255.0f;
            // Full range: chroma byte / 255 - 0.5, the inverse of cua-tracer-pyrowave's and XR Pilot's
            // encoders (tools/trace_roundtrip.cpp). Limited range: (byte - 128) / 224.
            const float Cb = limited_range ? (p.cb[c] - 128.0f) * cScale / 255.0f : p.cb[c] / 255.0f - 0.5f;
            const float Cr = limited_range ? (p.cr[c] - 128.0f) * cScale / 255.0f : p.cr[c] / 255.0f - 0.5f;
            uint8_t* o = &rgb[(size_t(y) * size_t(p.width) + size_t(x)) * 3];
            o[0] = unit(Y + 1.5748f * Cr);
            o[1] = unit(Y - 0.1873f * Cb - 0.4681f * Cr);
            o[2] = unit(Y + 1.8556f * Cb);
        }
    return rgb;
}
} // namespace pyrowave_pil
