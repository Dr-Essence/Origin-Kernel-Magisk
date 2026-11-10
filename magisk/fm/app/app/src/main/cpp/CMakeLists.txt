cmake_minimum_required(VERSION 3.22)
project(fmjni CXX)

# libfmjni from AOSP packages/apps/FMRadio/jni/fmr: talks to /dev/fm (MediaTek's FM driver).
# The AOSP build linked libcutils/libutils only for logging; here android/log.h does it
# (log_shim/utils/Log.h).
add_library(fmjni SHARED common.cpp fmr_core.cpp fmr_err.cpp libfm_jni.cpp layout_check.cpp)
target_include_directories(fmjni PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/log_shim)
target_compile_options(fmjni PRIVATE -Wno-unused-parameter -Wno-format)
target_link_libraries(fmjni log dl)
