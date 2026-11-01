/* Desktop platform identities shared by the game and launcher; plain C/C++. */
#ifndef OPENCNC3D_PLATFORM_H
#define OPENCNC3D_PLATFORM_H

#if defined(_WIN32)
#define OPENCNC3D_PLATFORM "windows"
#define OPENCNC3D_LIBRARY_SUFFIX ".dll"
#elif defined(__APPLE__)
#define OPENCNC3D_PLATFORM "macos"
#define OPENCNC3D_LIBRARY_SUFFIX ".dylib"
#elif defined(__linux__)
#define OPENCNC3D_PLATFORM "linux"
#define OPENCNC3D_LIBRARY_SUFFIX ".so"
#else
#error Unsupported desktop platform
#endif

#define OPENCNC3D_TD_LIBRARY "TiberianDawn" OPENCNC3D_LIBRARY_SUFFIX
#define OPENCNC3D_RA_LIBRARY "RedAlert" OPENCNC3D_LIBRARY_SUFFIX
#define OPENCNC3D_XL_LIBRARY "TiberianDawnXL" OPENCNC3D_LIBRARY_SUFFIX
#define OPENCNC3D_RA_PATH "ra3d/" OPENCNC3D_RA_LIBRARY

#endif
