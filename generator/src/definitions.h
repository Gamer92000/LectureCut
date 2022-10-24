#define VERSION "0.1.1"
#define DEFAULT_FFMPEG_LOG_LEVEL "quiet"


#ifdef _WIN32
  #define popen _popen
  #define pclose _pclose
#endif

#ifndef _WIN32
  #define fopen_s(fp, fmt, mode)          *(fp)=fopen( (fmt), (mode))
#endif
