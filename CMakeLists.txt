# pillow-pyrowave: the native decoder module. PyroWave (MIT) and the Granite subset its Vulkan library
# needs are pinned as in cua-tracer-pyrowave (V-Sekai-fire/interactor-cua-driver) and XR Pilot.
# macOS builds PyroWave's Metal port; Linux and Windows build the Vulkan library, which loads Vulkan
# at run time through volk, so no Vulkan SDK is needed to build.
cmake_minimum_required(VERSION 3.20)
project(pillow_pyrowave LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
include(FetchContent)
FetchContent_Declare(
    pyrowave
    GIT_REPOSITORY https://github.com/V-Sekai-fire/pyrowave.git
    GIT_TAG 89f7e47d4abbf650c91fae766728af866c5e32a0
    SOURCE_SUBDIR none
)
set(N ${CMAKE_CURRENT_SOURCE_DIR}/src/native)
# PILLOW_PYROWAVE_VULKAN builds the Vulkan back end on Apple too (MoltenVK), to test that path on a Mac.
option(PILLOW_PYROWAVE_VULKAN "Build the Vulkan back end on Apple (MoltenVK) instead of Metal" OFF)
if(APPLE AND NOT PILLOW_PYROWAVE_VULKAN)
    enable_language(OBJCXX)
    FetchContent_MakeAvailable(pyrowave)
    set(M ${pyrowave_SOURCE_DIR}/metal)
    add_library(pyrowave_metal STATIC
        ${M}/pyrowave_common.mm ${M}/pyrowave_decoder.mm ${M}/pyrowave_encoder.mm ${M}/pyrowave_bitstream.cpp)
    target_include_directories(pyrowave_metal PUBLIC ${M})
    target_compile_options(pyrowave_metal PRIVATE $<$<COMPILE_LANGUAGE:OBJCXX>:-fobjc-arc>)
    find_library(IOSURFACE_LIBRARY IOSurface REQUIRED)
    find_library(METAL_LIBRARY Metal REQUIRED)
    find_library(FOUNDATION_LIBRARY Foundation REQUIRED)
    target_link_libraries(pyrowave_metal PUBLIC ${IOSURFACE_LIBRARY} ${METAL_LIBRARY} ${FOUNDATION_LIBRARY} objc)
    Python_add_library(_pyrowave MODULE WITH_SOABI ${N}/module.cpp ${N}/decode.cpp ${N}/decode_metal.mm)
    target_compile_options(_pyrowave PRIVATE $<$<COMPILE_LANGUAGE:OBJCXX>:-fobjc-arc>)
    target_link_libraries(_pyrowave PRIVATE pyrowave_metal)
else()
    FetchContent_Declare(
        granite
        # Themaister/Granite 1b2d1801 plus one commit that lets util/timer.cpp build on macOS.
        GIT_REPOSITORY https://github.com/V-Sekai-fire/Granite.git
        GIT_TAG 0e9b26e2d0e6cc9b5ab1184782b0635571080c8e
        GIT_SUBMODULES third_party/volk third_party/khronos/vulkan-headers
        SOURCE_SUBDIR none
    )
    FetchContent_MakeAvailable(pyrowave granite)
    set(GRANITE_VULKAN_SHADER_MANAGER_RUNTIME_COMPILER OFF CACHE BOOL "" FORCE)
    set(GRANITE_SHADER_COMPILER_OPTIMIZE OFF CACHE BOOL "" FORCE)
    set(GRANITE_POSITION_INDEPENDENT ON CACHE BOOL "" FORCE)
    set(GRANITE_SHIPPING ON CACHE BOOL "" FORCE)
    set(GRANITE_VULKAN_SPIRV_CROSS OFF CACHE BOOL "" FORCE)
    set(GRANITE_VULKAN_SYSTEM_HANDLES OFF CACHE BOOL "" FORCE)
    set(GRANITE_RENDERER OFF CACHE BOOL "" FORCE)
    set(GRANITE_VULKAN_FOSSILIZE OFF CACHE BOOL "" FORCE)
    set(GRANITE_PLATFORM "null" CACHE STRING "" FORCE)
    add_subdirectory(${granite_SOURCE_DIR} ${CMAKE_BINARY_DIR}/_deps/granite-build EXCLUDE_FROM_ALL)
    add_library(pyrowave_vk STATIC
        ${pyrowave_SOURCE_DIR}/pyrowave_encoder.cpp
        ${pyrowave_SOURCE_DIR}/pyrowave_decoder.cpp
        ${pyrowave_SOURCE_DIR}/pyrowave_common.cpp
        ${pyrowave_SOURCE_DIR}/pyrowave_c.cpp
        ${granite_SOURCE_DIR}/video/scaler.cpp)
    target_include_directories(pyrowave_vk
        PUBLIC ${pyrowave_SOURCE_DIR}
        PRIVATE ${pyrowave_SOURCE_DIR}/shaders ${granite_SOURCE_DIR}/video)
    target_link_libraries(pyrowave_vk PUBLIC granite-vulkan granite-math)
    target_compile_definitions(pyrowave_vk PRIVATE PYROWAVE_PRECISION=1)
    Python_add_library(_pyrowave MODULE WITH_SOABI ${N}/module.cpp ${N}/decode.cpp ${N}/decode_vulkan.cpp)
    target_link_libraries(_pyrowave PRIVATE pyrowave_vk)
endif()
target_include_directories(_pyrowave PRIVATE ${N})
install(TARGETS _pyrowave LIBRARY DESTINATION pillow_pyrowave)
