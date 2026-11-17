/* Direct IOSurface host-memory import probe. No staging buffer is used. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <IOSurface/IOSurface.h>
#include <CoreFoundation/CoreFoundation.h>
#include <vulkan/vulkan.h>
#define CHECK(x) do { VkResult r=(x); if(r) { printf("FAIL %s: %d\n",#x,r);return 1;} } while(0)
int main(void) {
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="IOSurface host probe",.apiVersion=VK_API_VERSION_1_1};
    VkInstanceCreateInfo ic={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};
    VkInstance inst; CHECK(vkCreateInstance(&ic,NULL,&inst));
    VkPhysicalDevice pd;uint32_t n=1;CHECK(vkEnumeratePhysicalDevices(inst,&n,&pd));if(!n)return 2;
    uint32_t ne=0;CHECK(vkEnumerateDeviceExtensionProperties(pd,NULL,&ne,NULL));
    VkExtensionProperties *ext=calloc(ne,sizeof(*ext));CHECK(vkEnumerateDeviceExtensionProperties(pd,NULL,&ne,ext));
    int host=0;for(uint32_t i=0;i<ne;i++)if(!strcmp(ext[i].extensionName,VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME))host=1;free(ext);
    VkPhysicalDeviceExternalMemoryHostPropertiesEXT hp={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT};
    VkPhysicalDeviceProperties2 prop={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=&hp};vkGetPhysicalDeviceProperties2(pd,&prop);
    printf("device=%s host_import=%d alignment=%llu\n",prop.properties.deviceName,host,(unsigned long long)hp.minImportedHostPointerAlignment);fflush(stdout);
    if(!host) { puts("BLOCKED: VK_EXT_external_memory_host is not advertised");vkDestroyInstance(inst,NULL);return 77; }
    uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,NULL);VkQueueFamilyProperties *qs=calloc(nq,sizeof(*qs));vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,qs);
    uint32_t qi=0;while(qi<nq && !(qs[qi].queueFlags&(VK_QUEUE_COMPUTE_BIT|VK_QUEUE_GRAPHICS_BIT)))qi++;free(qs);if(qi==nq)return 3;
    float priority=1;VkDeviceQueueCreateInfo qc={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qi,.queueCount=1,.pQueuePriorities=&priority};
    const char *ename=VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME;
    VkDeviceCreateInfo dc={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qc,.enabledExtensionCount=1,.ppEnabledExtensionNames=&ename};
    VkDevice dev;CHECK(vkCreateDevice(pd,&dc,NULL,&dev));VkQueue queue;vkGetDeviceQueue(dev,qi,0,&queue);
    int w=1024,h=1024,row=w*4,bpe=4;const void *keys[]={kIOSurfaceWidth,kIOSurfaceHeight,kIOSurfaceBytesPerRow,kIOSurfaceBytesPerElement};
    CFNumberRef vals[]={CFNumberCreate(NULL,kCFNumberIntType,&w),CFNumberCreate(NULL,kCFNumberIntType,&h),CFNumberCreate(NULL,kCFNumberIntType,&row),CFNumberCreate(NULL,kCFNumberIntType,&bpe)};
    CFDictionaryRef desc=CFDictionaryCreate(NULL,keys,(const void **)vals,4,&kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
    IOSurfaceRef surf=IOSurfaceCreate(desc);CFRelease(desc);for(int i=0;i<4;i++)CFRelease(vals[i]);if(!surf)return 4;
    IOSurfaceLock(surf,0,NULL);uint32_t *base=IOSurfaceGetBaseAddress(surf);size_t size=IOSurfaceGetAllocSize(surf);memset(base,0,size);IOSurfaceUnlock(surf,0,NULL);
    PFN_vkGetMemoryHostPointerPropertiesEXT gethp=(void *)vkGetDeviceProcAddr(dev,"vkGetMemoryHostPointerPropertiesEXT");
    VkMemoryHostPointerPropertiesEXT hpp={.sType=VK_STRUCTURE_TYPE_MEMORY_HOST_POINTER_PROPERTIES_EXT};
    CHECK(gethp(dev,VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT,base,&hpp));
    VkExternalMemoryBufferCreateInfo eb={.sType=VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,.handleTypes=VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT};
    VkBufferCreateInfo bc={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.pNext=&eb,.size=size,.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    VkBuffer buf;CHECK(vkCreateBuffer(dev,&bc,NULL,&buf));VkMemoryRequirements mr;vkGetBufferMemoryRequirements(dev,buf,&mr);
    VkPhysicalDeviceMemoryProperties mp;vkGetPhysicalDeviceMemoryProperties(pd,&mp);uint32_t mt=0;
    for(;mt<mp.memoryTypeCount;mt++)if((hpp.memoryTypeBits&mr.memoryTypeBits&(1u<<mt)) && (mp.memoryTypes[mt].propertyFlags&VK_MEMORY_PROPERTY_HOST_COHERENT_BIT))break;
    if(mt==mp.memoryTypeCount || mr.size>size) { puts("FAIL no coherent import memory type / surface too small");return 5; }
    VkImportMemoryHostPointerInfoEXT imp={.sType=VK_STRUCTURE_TYPE_IMPORT_MEMORY_HOST_POINTER_INFO_EXT,.handleType=VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT,.pHostPointer=base};
    VkMemoryAllocateInfo ma={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.pNext=&imp,.allocationSize=size,.memoryTypeIndex=mt};
    VkDeviceMemory mem;CHECK(vkAllocateMemory(dev,&ma,NULL,&mem));CHECK(vkBindBufferMemory(dev,buf,mem,0));
    VkCommandPoolCreateInfo pc={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=qi};VkCommandPool pool;CHECK(vkCreateCommandPool(dev,&pc,NULL,&pool));
    VkCommandBufferAllocateInfo ca={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};VkCommandBuffer cmd;CHECK(vkAllocateCommandBuffers(dev,&ca,&cmd));
    VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};CHECK(vkBeginCommandBuffer(cmd,&begin));
    VkMemoryBarrier pre={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_HOST_WRITE_BIT,.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT|VK_ACCESS_TRANSFER_WRITE_BIT};
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_HOST_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,1,&pre,0,NULL,0,NULL);
    vkCmdFillBuffer(cmd,buf,0,size,0x5a93c741);
    VkMemoryBarrier post={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};
    vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&post,0,NULL,0,NULL);CHECK(vkEndCommandBuffer(cmd));
    VkFenceCreateInfo fc={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VkFence fence;CHECK(vkCreateFence(dev,&fc,NULL,&fence));
    VkSubmitInfo sub={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};CHECK(vkQueueSubmit(queue,1,&sub,fence));CHECK(vkWaitForFences(dev,1,&fence,VK_TRUE,5000000000ULL));
    IOSurfaceLock(surf,kIOSurfaceLockReadOnly,NULL);size_t bad=0;for(size_t i=0;i<size/4;i++)if(base[i]!=0x5a93c741)bad++;IOSurfaceUnlock(surf,kIOSurfaceLockReadOnly,NULL);
    printf("GPU fill -> original IOSurface: %zu / %zu wrong words\n",bad,size/4);
    /* CPU writes the first half. The GPU reads those same imported pages and
     * copies to the second half, which the CPU reads through the IOSurface.
     * Repeated patterns catch stale cache lines and early completion. */
    for (uint32_t round=1;round<=16 && !bad;round++) {
        size_t half=size/8;
        IOSurfaceLock(surf,0,NULL);
        for(size_t i=0;i<half;i++)base[i]=(uint32_t)i*3u+round*0x10203u;
        memset(base+half,0,size/2);
        IOSurfaceUnlock(surf,0,NULL);
        CHECK(vkResetCommandPool(dev,pool,0));CHECK(vkResetFences(dev,1,&fence));
        CHECK(vkBeginCommandBuffer(cmd,&begin));
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_HOST_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,1,&pre,0,NULL,0,NULL);
        VkBufferCopy region={.srcOffset=0,.dstOffset=size/2,.size=size/2};
        vkCmdCopyBuffer(cmd,buf,buf,1,&region);
        vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&post,0,NULL,0,NULL);
        CHECK(vkEndCommandBuffer(cmd));CHECK(vkQueueSubmit(queue,1,&sub,fence));
        CHECK(vkWaitForFences(dev,1,&fence,VK_TRUE,5000000000ULL));
        IOSurfaceLock(surf,kIOSurfaceLockReadOnly,NULL);
        for(size_t i=0;i<half;i++)if(base[half+i]!=(uint32_t)i*3u+round*0x10203u)bad++;
        IOSurfaceUnlock(surf,kIOSurfaceLockReadOnly,NULL);
    }
    printf("CPU -> imported pages -> GPU -> same IOSurface: %s\n",bad?"FAIL":"PASS (16 patterns)");
    vkDestroyFence(dev,fence,NULL);vkDestroyCommandPool(dev,pool,NULL);vkDestroyBuffer(dev,buf,NULL);vkFreeMemory(dev,mem,NULL);CFRelease(surf);vkDestroyDevice(dev,NULL);vkDestroyInstance(inst,NULL);
    return bad?6:0;
}
