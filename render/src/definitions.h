#pragma once

#define VERSION "0.1.0"
#define DEFAULT_FFMPEG_LOG_LEVEL "error"

#ifdef _WIN32
#define popen _popen
#define pclose _pclose
#endif

#ifdef NDEBUG
#  define assert(condition) ((void)0)
#else
#  define assert(condition) /*implementation defined*/
#endif