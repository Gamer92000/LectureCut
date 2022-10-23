#if defined(_MSC_VER)
  //  Microsoft 
  #define EXPORT __declspec(dllexport)
#elif defined(__GNUC__)
  //  GCC
  #define EXPORT __attribute__((visibility("default")))
#else
  #define EXPORT
  #pragma warning Unknown dynamic link export semantics.
#endif

#ifdef __cplusplus
extern "C" {
#endif

  const char EXPORT *version();

  void EXPORT init(const char* ffmpeg_log_level);

  struct cut
  {
    double start;
    double end;
  };

  struct cut_list
  {
    long num_cuts;
    cut* cuts;
  };

  // takes the given file and converts it to pcm audio
  // the audio is then processed by webrtcvad to
  // determine the speech segments
  cut_list EXPORT generate(const char *file, void (*progress)(const char*, double));

#ifdef __cplusplus
}
#endif