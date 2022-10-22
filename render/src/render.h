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

  void EXPORT init();

  struct cut
  {
    double start;
    double end;
  };

  // prepare gets called before rendering is started
  // it returns an arbitrary id that needs to be passed to render
  // internlly, prepare can do whatever can be done before getting
  // the final cut list (e.g. load the file, segment it, etc.)
  int EXPORT prepare(const char *file);

  // render gets once the cut list is known
  // it renders the file and returns once it's done
  void EXPORT render(int process, long num_cuts, cut* cuts, const char *output);

#ifdef __cplusplus
}
#endif