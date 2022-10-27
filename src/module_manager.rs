extern crate libloading;

use std::ffi::CStr;
use std::ffi::CString;
use std::ffi::c_char;
use std::ffi::c_double;
use std::ffi::c_int;
use std::ffi::c_long;
use std::ffi::c_void;

use self::libloading::Symbol;

use self::libloading::Library;

pub struct Cut {
  pub start: c_double,
  pub end: c_double,
}

pub struct CutList {
  pub length: c_long,
  pub cuts: *const Cut,
}

pub struct GeneratorStats {
  pub len_pre_cut: c_double,
  pub len_post_cut: c_double,
}

pub struct GeneratorResult {
  pub cuts: CutList,
  pub stats: GeneratorStats,
}

type Callback = unsafe extern fn(*const c_char, c_double) -> ();

type InitFunc<'a> = Symbol<'a, unsafe extern fn(*const c_char) -> ()>;
type VersionFunc<'a> = Symbol<'a, unsafe extern fn() -> *const c_char>;
type PrepareFunc<'a> = Symbol<'a, unsafe extern fn(*const c_char, Callback) -> *const c_char>;
type RenderFunc<'a> = Symbol<'a, unsafe extern fn(*const c_char, *const c_char, CutList, c_int, Callback) -> c_void>;
type GenerateFunc<'a> = Symbol<'a, unsafe extern fn(*const c_char, c_int, bool, Callback) -> GeneratorResult>;

// quiet log level
const FFMPEG_LOG_LVL: &[u8] = b"error\0";

pub unsafe fn load_render() -> Library {
  // load render so from modules/render.so (render.dll)
  let mut lib_path = "modules/librender.so";
  if cfg!(windows) {
    lib_path = "modules/render.dll";
  }
  
  let lib = Library::new(lib_path).unwrap();

  let init: InitFunc = lib.get(b"init").unwrap();
  
  init(FFMPEG_LOG_LVL.as_ptr() as *const c_char);
  
  lib
}

pub unsafe fn render_prepare(lib: &Library, input: &str, progress: Callback) -> String {
  let prepare: PrepareFunc = lib.get(b"prepare").unwrap();
  let input = CString::new(input).unwrap();
  let output = prepare(input.as_ptr(), progress);
  let output = CStr::from_ptr(output).to_str().unwrap();
  output.to_string()
}

pub unsafe fn render_render(lib: &Library, process: String, output: &str, cuts: CutList, reencode: c_int, progress: Callback) {
  let render: RenderFunc = lib.get(b"render").unwrap();
  let input = CString::new(process).unwrap();
  let output = CString::new(output).unwrap();
  render(input.as_ptr(), output.as_ptr(), cuts, reencode, progress);
}

pub unsafe fn load_generator() -> Library {
  // load generator so from modules/generator.so (generator.dll)
  let mut lib_path = "modules/libgenerator.so";
  if cfg!(windows) {
    lib_path = "modules/generator.dll";
  }
  
  let lib = Library::new(lib_path).unwrap();
  
  let init: InitFunc = lib.get(b"init").unwrap();

  init(FFMPEG_LOG_LVL.as_ptr() as *const c_char);

  lib
}

pub unsafe fn generator_generate(lib: &Library, input: &str, aggressiveness: c_int, invert: bool, progress: Callback) -> GeneratorResult {
  let generate: GenerateFunc = lib.get(b"generate").unwrap();
  let input = CString::new(input).unwrap();
  generate(input.as_ptr(), aggressiveness, invert, progress)
}

pub unsafe fn module_version(lib: &Library) -> String {
  let version: VersionFunc = lib.get(b"version").unwrap();
  let version = version();
  let version = CStr::from_ptr(version).to_str().unwrap();
  version.to_string()
}