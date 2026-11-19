#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <IOSurface/IOSurface.h>
#import <IOKit/IOKitLib.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <dlfcn.h>
int main(int argc, char **argv) { @autoreleasepool {
    int w=argc>1?atoi(argv[1]):64, h=argc>2?atoi(argv[2]):64;
    if(w<=0 || h<=0 || w>4096 || h>4096 || w%8)return 10;
    size_t count=(size_t)w*h, bytes=count*4;
    const char *plugin=getenv("NM_TEST_PLUGIN");
    if(!plugin)plugin="/Library/GPUBundles/NVMTLDriver.bundle/Contents/MacOS/NVMTLDriver";
    if(!dlopen(plugin,RTLD_NOW|RTLD_LOCAL)) {puts(dlerror());return 1;}
    io_service_t svc=IOServiceGetMatchingService(kIOMainPortDefault,IOServiceMatching("NMXAccel"));
    id<MTLDevice> dev=((id(*)(id,SEL,mach_port_t))objc_msgSend)([NSClassFromString(@"NVMTLDevice") alloc],NSSelectorFromString(@"initWithAcceleratorPort:"),svc);
    if(!dev)return 2;IOObjectRelease(svc);
    NSDictionary *desc=@{(id)kIOSurfaceWidth:@(w),(id)kIOSurfaceHeight:@(h),
        (id)kIOSurfaceBytesPerRow:@(w*4),(id)kIOSurfaceBytesPerElement:@4,
        (id)kIOSurfacePixelFormat:@(0x42475241)};
    IOSurfaceRef surf=IOSurfaceCreate((__bridge CFDictionaryRef)desc);if(!surf)return 3;
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:w height:h mipmapped:NO];
    td.usage=MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget;
    id<MTLTexture> tex=[dev newTextureWithDescriptor:td iosurface:surf plane:0];if(!tex)return 4;
    Ivar iv=class_getInstanceVariable(object_getClass(tex),"_hostImg");
    BOOL direct=iv?*(BOOL *)((char *)(__bridge void *)tex+ivar_getOffset(iv)):NO;
    printf("Metal texture aliases IOSurface pages: %s\n",direct?"YES":"NO");fflush(stdout);
    if(!direct)return 5;
    id<MTLCommandQueue> q=[dev newCommandQueue];
    MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture=tex;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].storeAction=MTLStoreActionStore;rp.colorAttachments[0].clearColor=MTLClearColorMake(0,1,0,1);
    id<MTLCommandBuffer> cb=[q commandBuffer];id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];[enc endEncoding];[cb commit];[cb waitUntilCompleted];
    if(cb.status!=MTLCommandBufferStatusCompleted)return 6;
    IOSurfaceLock(surf,kIOSurfaceLockReadOnly,NULL);uint32_t *base=IOSurfaceGetBaseAddress(surf);size_t bad=0;
    for(int i=0;(size_t)i<count;i++)if(base[i]!=0xff00ff00u)bad++;
    IOSurfaceUnlock(surf,kIOSurfaceLockReadOnly,NULL);
    printf("GPU render clear -> original IOSurface: %zu wrong pixels\n",bad);if(bad)return 7;
    IOSurfaceLock(surf,0,NULL);for(int i=0;(size_t)i<count;i++)base[i]=0xff4b3521u;IOSurfaceUnlock(surf,0,NULL);
    id<MTLBuffer> readback=[dev newBufferWithLength:bytes options:MTLResourceStorageModeShared];
    cb=[q commandBuffer];id<MTLBlitCommandEncoder> blit=[cb blitCommandEncoder];
    [blit copyFromTexture:tex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
      sourceSize:MTLSizeMake(w,h,1) toBuffer:readback destinationOffset:0 destinationBytesPerRow:w*4 destinationBytesPerImage:bytes];
    [blit endEncoding];[cb commit];[cb waitUntilCompleted];if(cb.status!=MTLCommandBufferStatusCompleted)return 8;
    uint32_t *data=readback.contents;for(int i=0;(size_t)i<count;i++)if(data[i]!=0xff4b3521u)bad++;
    printf("CPU IOSurface writes -> GPU texture reads: %zu wrong pixels\n",bad);
    CFRelease(surf);return bad?9:0;
} }
