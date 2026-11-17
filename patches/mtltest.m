#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <MetalPerformanceShaders/MetalPerformanceShaders.h>
#include <stdio.h>
#include <stdint.h>

static void print_grid(const char *name, const uint8_t *px, int n) {
    printf("=== %s (%dx%d) ===\n", name, n, n);
    for (int y = 0; y < n; y++) {
        for (int x = 0; x < n; x++) {
            uint8_t g = px[(y * n + x) * 4 + 1];
            putchar(g > 128 ? '#' : '.');
        }
        putchar('\n');
    }
}

int main(void) {
    @autoreleasepool {
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { printf("no device\n"); return 1; }
        printf("device: %s\n", dev.name.UTF8String);
        id<MTLCommandQueue> q = [dev newCommandQueue];

        NSString *src = @
            "#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "struct VOut { float4 pos [[position]]; float2 uv; };\n"
            "vertex VOut v_main(uint vid [[vertex_id]]) {\n"
            "  float2 p[4] = { {-1,-1}, {1,-1}, {-1,1}, {1,1} };\n"
            "  VOut o; o.pos = float4(p[vid], 0, 1); o.uv = p[vid]; return o;\n"
            "}\n"
            "fragment float4 f_circle(VOut in [[stage_in]]) {\n"
            "  return length(in.uv) <= 0.65 ? float4(0,1,0,1) : float4(0,0,0,1);\n"
            "}\n"
            "fragment float4 f_pow_circle(VOut in [[stage_in]]) {\n"
            "  float d = pow(abs(in.uv.x), 2.0) + pow(abs(in.uv.y), 2.0);\n"
            "  return d <= 0.4225 ? float4(0,1,0,1) : float4(0,0,0,1);\n"
            "}\n"
            "fragment float4 f_fbfetch(VOut in [[stage_in]], float4 prev [[color(0)]]) {\n"
            "  return prev + float4(0, 0.5, 0, 0);\n"
            "}\n"
            "fragment float4 f_tex_a8(VOut in [[stage_in]], texture2d<float> t [[texture(0)]]) {\n"
            "  constexpr sampler s(coord::normalized, filter::linear);\n"
            "  float a = t.sample(s, in.uv * 0.5 + 0.5).a;\n"
            "  return float4(0, a, 0, 1);\n"
            "}\n"
            "fragment half4 f16_circle(VOut in [[stage_in]]) {\n"
            "  half2 uv = half2(in.uv);\n"
            "  return length(uv) <= half(0.65) ? half4(0,1,0,1) : half4(0,0,0,1);\n"
            "}\n"
            "fragment half4 f16_pow_circle(VOut in [[stage_in]]) {\n"
            "  half2 uv = half2(in.uv);\n"
            "  half d = pow(abs(uv.x), half(2.0)) + pow(abs(uv.y), half(2.0));\n"
            "  return d <= half(0.4225) ? half4(0,1,0,1) : half4(0,0,0,1);\n"
            "}\n"
            "fragment half4 f16_fbfetch(VOut in [[stage_in]], half4 prev [[color(0)]]) {\n"
            "  return prev + half4(0, 0.5, 0, 0);\n"
            "}\n";

        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
        if (!lib) { printf("compile err: %s\n", err.localizedDescription.UTF8String); return 1; }

        // 1. f_circle, f_pow_circle, f_fbfetch + f16 variants
        const char *frags[6] = { "f_circle", "f_pow_circle", "f_fbfetch", "f16_circle", "f16_pow_circle", "f16_fbfetch" };
        for (int k = 0; k < 6; k++) {
            MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:16 height:16 mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
            MTLRenderPipelineDescriptor *rpd = [MTLRenderPipelineDescriptor new];
            rpd.vertexFunction = [lib newFunctionWithName:@"v_main"];
            rpd.fragmentFunction = [lib newFunctionWithName:[NSString stringWithUTF8String:frags[k]]];
            rpd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
            id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rpd error:&err];
            if (!pso) { printf("%s pso err: %s\n", frags[k], err.localizedDescription.UTF8String); continue; }

            id<MTLCommandBuffer> cb = [q commandBuffer];
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = tex;
            rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].clearColor = (k == 2 || k == 5) ? MTLClearColorMake(0.5, 0, 0, 1) : MTLClearColorMake(0, 0, 0, 1);
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            [enc drawPrimitives:MTLPrimitiveTypeTriangleStrip vertexStart:0 vertexCount:4];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];

            uint8_t px[16 * 16 * 4] = {};
            [tex getBytes:px bytesPerRow:16 * 4 fromRegion:MTLRegionMake2D(0, 0, 16, 16) mipmapLevel:0];
            if (k != 2 && k != 5) {
                print_grid(frags[k], px, 16);
            } else {
                printf("%s center BGRA: %u %u %u %u (want ~0 128 128 255)\n", frags[k],
                       px[(8*16+8)*4+0], px[(8*16+8)*4+1], px[(8*16+8)*4+2], px[(8*16+8)*4+3]);
            }
        }

        // 2. MPSImageGaussianBlur
        {
            MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:32 height:32 mipmapped:NO];
            td.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
            id<MTLTexture> s = [dev newTextureWithDescriptor:td];
            id<MTLTexture> d = [dev newTextureWithDescriptor:td];
            uint8_t inpx[32 * 32 * 4];
            memset(inpx, 255, sizeof(inpx));
            [s replaceRegion:MTLRegionMake2D(0, 0, 32, 32) mipmapLevel:0 withBytes:inpx bytesPerRow:32 * 4];
            MPSImageGaussianBlur *blur = [[MPSImageGaussianBlur alloc] initWithDevice:dev sigma:3.0f];
            id<MTLCommandBuffer> cb = [q commandBuffer];
            [blur encodeToCommandBuffer:cb sourceTexture:s destinationTexture:d];
            [cb commit];
            [cb waitUntilCompleted];
            uint8_t outpx[32 * 32 * 4] = {};
            [d getBytes:outpx bytesPerRow:32 * 4 fromRegion:MTLRegionMake2D(0, 0, 32, 32) mipmapLevel:0];
            printf("MPSBlur BGRA center: %u %u %u %u (want 255 255 255 255)\n",
                   outpx[(16*32+16)*4+0], outpx[(16*32+16)*4+1], outpx[(16*32+16)*4+2], outpx[(16*32+16)*4+3]);
        }

        // 3. A8Unorm sampling
        {
            MTLTextureDescriptor *a8d = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatA8Unorm width:16 height:16 mipmapped:NO];
            a8d.usage = MTLTextureUsageShaderRead;
            id<MTLTexture> a8 = [dev newTextureWithDescriptor:a8d];
            uint8_t a8px[16 * 16];
            memset(a8px, 200, sizeof(a8px));
            [a8 replaceRegion:MTLRegionMake2D(0, 0, 16, 16) mipmapLevel:0 withBytes:a8px bytesPerRow:16];

            MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:16 height:16 mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
            id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
            MTLRenderPipelineDescriptor *rpd = [MTLRenderPipelineDescriptor new];
            rpd.vertexFunction = [lib newFunctionWithName:@"v_main"];
            rpd.fragmentFunction = [lib newFunctionWithName:@"f_tex_a8"];
            rpd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
            id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rpd error:&err];
            id<MTLCommandBuffer> cb = [q commandBuffer];
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = tex;
            rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
            rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            [enc setFragmentTexture:a8 atIndex:0];
            [enc drawPrimitives:MTLPrimitiveTypeTriangleStrip vertexStart:0 vertexCount:4];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            uint8_t px[16 * 16 * 4] = {};
            [tex getBytes:px bytesPerRow:16 * 4 fromRegion:MTLRegionMake2D(0, 0, 16, 16) mipmapLevel:0];
            printf("A8Unorm sample BGRA center: %u %u %u %u (want 0 200 0 255)\n",
                   px[(8*16+8)*4+0], px[(8*16+8)*4+1], px[(8*16+8)*4+2], px[(8*16+8)*4+3]);
        }
    }
    return 0;
}
