cmake_minimum_required(VERSION 3.22)
project(subplayer_whisper C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# whisper.cpp pinned to an exact commit (tag v1.9.5) - cannot be changed upstream.
include(FetchContent)
FetchContent_Declare(
    whispercpp
    GIT_REPOSITORY https://github.com/ggml-org/whisper.cpp.git
    GIT_TAG        d1be6fde11ac6e0407606b4e42fe72d34add8037
    GIT_SHALLOW    FALSE
)

set(BUILD_SHARED_LIBS        OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_TESTS      OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES   OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER     OFF CACHE BOOL "" FORCE)
set(WHISPER_ALL_WARNINGS     OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE              OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP              OFF CACHE BOOL "" FORCE)
set(GGML_BUILD_TESTS         OFF CACHE BOOL "" FORCE)
set(GGML_BUILD_EXAMPLES      OFF CACHE BOOL "" FORCE)
if (ANDROID_ABI STREQUAL "arm64-v8a")
    # ARMv8.2 (fp16 + dot product): ~2x faster. The app checks the CPU supports
    # it before loading this library (all phones from ~2018 onward do).
    set(GGML_CPU_ARM_ARCH "armv8.2-a+fp16+dotprod" CACHE STRING "" FORCE)
endif()

FetchContent_MakeAvailable(whispercpp)

add_library(whisper_jni SHARED whisper_jni.cpp)
target_link_libraries(whisper_jni PRIVATE whisper log)
target_compile_options(whisper_jni PRIVATE -O3)

# 16 KB memory pages (Google Play requirement for apps targeting Android 15+)
target_link_options(whisper_jni PRIVATE "-Wl,-z,max-page-size=16384")
