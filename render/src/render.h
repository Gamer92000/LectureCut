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

  EXPORT const char* version();

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

  typedef void progress_callback(const char*, double);

  // prepare gets called before rendering is started
  // it returns an arbitrary id that needs to be passed to render
  // internlly, prepare can do whatever can be done before getting
  // the final cut list (e.g. load the file, segment it, etc.)
  EXPORT const char *prepare(
    const char *file,
    progress_callback *progress
  );

  // render gets once the cut list is known
  // it renders the file and returns once it's done
  EXPORT void render(
    const char *process,
    const char *output,
    cut_list cuts,
    int quality,
    progress_callback *progress
  );

#ifdef __cplusplus
}
#endif