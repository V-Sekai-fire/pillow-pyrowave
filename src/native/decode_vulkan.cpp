// Vulkan back end (Linux, Windows): PyroWave's Vulkan library loads Vulkan at run time through volk and
// decodes straight into CPU planes. One PyroWave device is kept for the process.
#include "decode.hpp"
#include <cstdint>
#include <mutex>
#include <vulkan/vulkan_core.h> // pyrowave.h needs the Vulkan types first
#include "pyrowave.h"

namespace pyrowave_pil
{
namespace
{
struct Gpu
{
    pyrowave_device device = nullptr;
    std::string error;
};

Gpu& gpu()
{
    static Gpu g;
    static std::once_flag once;
    std::call_once(once, [] {
        if (pyrowave_create_default_device(&g.device) != PYROWAVE_SUCCESS)
            g.error = "no PyroWave-capable Vulkan device";
    });
    return g;
}

pyrowave_cpu_buffer cpuBuffer(Planes& p)
{
    pyrowave_cpu_buffer b = {};
    b.data[0] = p.y.data();
    b.data[1] = p.cb.data();
    b.data[2] = p.cr.data();
    b.row_stride_in_bytes[0] = size_t(p.width);
    b.row_stride_in_bytes[1] = b.row_stride_in_bytes[2] = size_t(p.chromaWidth());
    b.plane_size_in_bytes[0] = p.y.size();
    b.plane_size_in_bytes[1] = p.cb.size();
    b.plane_size_in_bytes[2] = p.cr.size();
    b.width = p.width;
    b.height = p.height;
    b.format = p.chroma_444 ? PYROWAVE_CPU_BUFFER_FORMAT_YUV444P : PYROWAVE_CPU_BUFFER_FORMAT_YUV420P;
    return b;
}
} // namespace

std::string decodePlanes(const uint8_t* data, size_t size, const Header& h, Planes& out)
{
    Gpu& g = gpu();
    if (!g.error.empty())
        return g.error;
    pyrowave_decoder_create_info info = {};
    info.device = g.device;
    info.width = h.width;
    info.height = h.height;
    info.chroma = h.chroma_444 ? PYROWAVE_CHROMA_SUBSAMPLING_444 : PYROWAVE_CHROMA_SUBSAMPLING_420;
    info.fragment_path = false;
    pyrowave_decoder decoder = nullptr;
    if (pyrowave_decoder_create(&info, &decoder) != PYROWAVE_SUCCESS)
        return "pyrowave_decoder_create failed";
    out = sized(h);
    const pyrowave_cpu_buffer buffer = cpuBuffer(out);
    std::string error;
    if (pyrowave_decoder_push_packet(decoder, data, size) != PYROWAVE_SUCCESS)
        error = "the packet does not parse";
    else if (!pyrowave_decoder_decode_is_ready(decoder, false))
        error = "the packet does not hold a complete frame";
    else if (pyrowave_decoder_decode_cpu_buffer_synchronous(decoder, &buffer) != PYROWAVE_SUCCESS)
        error = "pyrowave_decoder_decode_cpu_buffer_synchronous failed";
    pyrowave_decoder_destroy(decoder);
    return error;
}
} // namespace pyrowave_pil
