extern crate libloading;

use std::ffi::CStr;
use std::ffi::CString;
use std::ffi::c_char;
use std::ffi::c_double;
use std::ffi::c_int;
use std::ffi::c_long;
use std::ffi::c_void;
use std::path::Path;

use crate::printer::raise_error;

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

#[derive(Clone)]
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

pub fn load_render() -> Library {
  // load render so from modules/render.so (render.dll)
  let mut lib_path = "modules/librender.so";
  if cfg!(windows) {
    lib_path = "modules/render.dll";
  }
  if cfg!(target_os = "macos") {
    lib_path = "modules/librender.dylib";
  }
  let binding = std::env::current_exe().unwrap();
  let binding = binding.parent().unwrap().join(lib_path);
  lib_path = binding.to_str().unwrap();
  
  if !Path::new(lib_path).exists() {
    raise_error(format!("{} does not exist. Please compile the render module first.", lib_path).as_str());
  }
  
  let lib: Library = unsafe { Library::new(lib_path).unwrap() };

  let init: InitFunc = unsafe { lib.get(b"init").unwrap() };
  
  unsafe {
    init(FFMPEG_LOG_LVL.as_ptr() as *const c_char);
  }
  
  lib
}

pub fn render_prepare(lib: &Library, input: &str, progress: Callback) -> String {
  let prepare: PrepareFunc = unsafe { lib.get(b"prepare").unwrap() };
  let input = CString::new(input).unwrap();
  let output = unsafe { prepare(input.as_ptr(), progress) };
  let output = unsafe { CStr::from_ptr(output) };
  output.to_str().unwrap().to_string()
}

pub fn render_render(lib: &Library, process: String, output: &str, cuts: CutList, reencode: c_int, progress: Callback) {
  let render: RenderFunc = unsafe { lib.get(b"render").unwrap() };
  let input = CString::new(process).unwrap();
  let output = CString::new(output).unwrap();
  unsafe { render(input.as_ptr(), output.as_ptr(), cuts, reencode, progress) };
}

pub fn load_generator() -> Library {
  // load generator so from modules/generator.so (generator.dll)
  
  let mut lib_path = "modules/libgenerator.so";
  if cfg!(windows) {
    lib_path = "modules/generator.dll";
  }
  if cfg!(target_os = "macos") {
    lib_path = "modules/libgenerator.dylib";
  }
  let binding = std::env::current_exe().unwrap();
  let binding = binding.parent().unwrap().join(lib_path);
  lib_path = binding.to_str().unwrap();

  if !Path::new(lib_path).exists() {
    raise_error(format!("{} does not exist. Please compile the generator module first.", lib_path).as_str());
  }
  
  let lib = unsafe { Library::new(lib_path).unwrap() };
  
  let init: InitFunc = unsafe { lib.get(b"init").unwrap() };

  unsafe {
    init(FFMPEG_LOG_LVL.as_ptr() as *const c_char);
  }

  lib
}

pub fn generator_generate(lib: &Library, input: &str, aggressiveness: c_int, invert: bool, progress: Callback) -> GeneratorResult {
  let generate: GenerateFunc = unsafe { lib.get(b"generate").unwrap() };
  let input = CString::new(input).unwrap();
  unsafe { generate(input.as_ptr(), aggressiveness, invert, progress) }
}

pub fn module_version(lib: &Library) -> String {
  let version: VersionFunc = unsafe { lib.get(b"version").unwrap() };
  let version = unsafe { version() };
  let version = unsafe { CStr::from_ptr(version) };
  version.to_str().unwrap().to_string()
}