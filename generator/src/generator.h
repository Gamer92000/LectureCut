#pragma once

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

  EXPORT const char *version();

  EXPORT void init(const char* ffmpeg_log_level);

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

  struct generator_stats
  {
    double len_pre_cuts;
    double len_post_cuts;
  };

  struct result
  {
    cut_list cuts;
    generator_stats stats;
  };

  typedef void progress_callback(const char*, double);

  // takes the given file and converts it to pcm audio
  // the audio is then processed by webrtcvad to
  // determine the speech segments
  EXPORT result generate(
    const char *file,
    int aggressiveness,
    bool invert,
    progress_callback* progress
  );

#ifdef __cplusplus
}
#endif