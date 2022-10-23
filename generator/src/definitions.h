#define VERSION "0.1.0"
#define DEFAULT_FFMPEG_LOG_LEVEL "quiet"


#ifdef _WIN32
  #define popen _popen
  #define pclose _pclose
#endif