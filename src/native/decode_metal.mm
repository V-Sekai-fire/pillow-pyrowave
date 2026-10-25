// Metal back end: PyroWave's Metal port decodes into GPU textures, so this keeps one MTLDevice,
// command queue and PyroWave device for the process, and reads the planes back after each frame.
#include "decode.hpp"
#include "pyrowave_metal.h"
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <mutex>

namespace pyrowave_pil
{
namespace
{
struct Gpu
{
    id<MTLDevice> mtl = nil;
    id<MTLCommandQueue> queue = nil;
    pyrowave_device device = nullptr;
    std::string error;
};

Gpu& gpu()
{
    static Gpu g;
    static std::once_flag once;
    std::call_once(once, [] {
        g.mtl = MTLCreateSystemDefaultDevice();
        if (!g.mtl)
        {
            g.error = "no Metal device";
            return;
        }
        if (!pyrowave_device_is_supported((__bridge void*)g.mtl))
        {
            g.error = "the Metal device cannot run PyroWave (needs Apple7 family, 32-wide SIMD groups)";
            return;
        }
        pyrowave_device_create_info info = {};
        info.mtl_device = (__bridge void*)g.mtl;
        if (pyrowave_device_create(&info, &g.device) != PYROWAVE_SUCCESS)
        {
            g.error = "pyrowave_device_create failed";
            return;
        }
        g.queue = [g.mtl newCommandQueue];
    });
    return g;
}

id<MTLTexture> plane(id<MTLDevice> mtl, int w, int h)
{
    MTLTextureDescriptor* d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR8Unorm
                                                                                 width:NSUInteger(w)
                                                                                height:NSUInteger(h)
                                                                             mipmapped:NO];
    d.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
    d.storageMode = MTLStorageModeShared;
    return [mtl newTextureWithDescriptor:d];
}

void read(id<MTLTexture> t, std::vector<uint8_t>& out, int w, int h)
{
    [t getBytes:out.data()
        bytesPerRow:NSUInteger(w)
         fromRegion:MTLRegionMake2D(0, 0, NSUInteger(w), NSUInteger(h))
        mipmapLevel:0];
}
} // namespace

std::string decodePlanes(const uint8_t* data, size_t size, const Header& h, Planes& out)
{
    Gpu& g = gpu();
    if (!g.error.empty())
        return g.error;
    @autoreleasepool
    {
        pyrowave_decoder_create_info info = {};
        info.device = g.device;
        info.width = h.width;
        info.height = h.height;
        info.chroma = h.chroma_444 ? PYROWAVE_CHROMA_SUBSAMPLING_444 : PYROWAVE_CHROMA_SUBSAMPLING_420;
        pyrowave_decoder decoder = nullptr;
        if (pyrowave_decoder_create(&info, &decoder) != PYROWAVE_SUCCESS)
            return "pyrowave_decoder_create failed";
        std::string error;
        if (pyrowave_decoder_push_packet(decoder, data, size) != PYROWAVE_SUCCESS)
            error = "the packet does not parse";
        else if (!pyrowave_decoder_decode_is_ready(decoder, false))
            error = "the packet does not hold a complete frame";
        if (error.empty())
        {
            out = sized(h);
            id<MTLTexture> y = plane(g.mtl, out.width, out.height);
            id<MTLTexture> cb = plane(g.mtl, out.chromaWidth(), out.chromaHeight());
            id<MTLTexture> cr = plane(g.mtl, out.chromaWidth(), out.chromaHeight());
            pyrowave_gpu_buffers buffers = {};
            buffers.planes[0] = (__bridge void*)y;
            buffers.planes[1] = (__bridge void*)cb;
            buffers.planes[2] = (__bridge void*)cr;
            id<MTLCommandBuffer> cmd = [g.queue commandBuffer];
            if (pyrowave_decoder_decode_gpu_buffer(decoder, (__bridge void*)cmd, &buffers) != PYROWAVE_SUCCESS)
                error = "pyrowave_decoder_decode_gpu_buffer failed";
            else
            {
                [cmd commit];
                [cmd waitUntilCompleted];
                if (cmd.status != MTLCommandBufferStatusCompleted)
                    error = "the decode command buffer did not complete";
                else
                {
                    read(y, out.y, out.width, out.height);
                    read(cb, out.cb, out.chromaWidth(), out.chromaHeight());
                    read(cr, out.cr, out.chromaWidth(), out.chromaHeight());
                }
            }
        }
        pyrowave_decoder_destroy(decoder);
        return error;
    }
}
} // namespace pyrowave_pil
