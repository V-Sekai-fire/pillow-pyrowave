// Decodes one PyroWave intra frame to 8-bit RGB. Shared by the Metal and Vulkan back ends: the header
// parse, the plane layout and the YCbCr to RGB conversion live here; each back end fills the planes.
#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace pyrowave_pil
{
// The 8-byte sequence header that opens every PyroWave frame (BitstreamSequenceHeader in PyroWave's
// pyrowave_common.hpp), read field by field from its two little-endian words.
struct Header
{
    int width = 0;
    int height = 0;
    bool extended = false;
    uint32_t total_blocks = 0;
    int code = 0;
    bool chroma_444 = false;
    int color_primaries = 0;   // 0 BT.709, 1 BT.2020
    int transfer_function = 0; // 0 BT.709, 1 PQ
    int ycbcr_transform = 0;   // 0 BT.709, 1 BT.2020
    bool limited_range = false;
    int chroma_siting = 0;     // 0 center, 1 left
};

bool parseHeader(const uint8_t* data, size_t size, Header& out);

// Empty when the header is one this package converts to sRGB RGB; otherwise the reason it is not.
std::string unsupported(const Header& h);

struct Planes
{
    int width = 0;
    int height = 0;
    bool chroma_444 = false;
    std::vector<uint8_t> y, cb, cr;
    int chromaWidth() const { return chroma_444 ? width : width / 2; }
    int chromaHeight() const { return chroma_444 ? height : height / 2; }
};

Planes sized(const Header& h);

// BT.709 YCbCr (full or limited range) to 8-bit RGB, chroma taken from the co-sited sample.
std::vector<uint8_t> toRgb(const Planes& p, bool limited_range);

// Back end: decode the packet into planes sized for its header. Returns an empty string on success,
// otherwise the reason the frame could not be decoded.
std::string decodePlanes(const uint8_t* data, size_t size, const Header& h, Planes& out);
} // namespace pyrowave_pil
