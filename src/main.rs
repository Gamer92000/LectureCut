extern crate libloading;
extern crate console;

mod argmunents;
mod printer;
mod helper;
mod module_manager;

use std::path::Path;

use argmunents::{parse_args, validate_args, Options};
use self::console::Term;
use self::console::style;
use crate::module_manager::generator_generate;
use crate::module_manager::render_render;

use self::libloading::Library;
use module_manager::{load_render, load_generator, module_version, render_prepare};
use printer::{greetings, print_non_mp4_warning};

use std::ffi::c_char;
use std::ffi::c_double;

unsafe fn run(options: Options, generator: &Library, render: &Library) {
  let term = Term::stdout();

  term.write_line(format!(" Input: {}", style(&options.input).yellow()).as_str()).unwrap();
  term.write_line(format!("Output: {}", style(&options.output).yellow()).as_str()).unwrap();

  if tree_magic::from_filepath(Path::new(options.input.as_str())) != "video/mp4" {
    print_non_mp4_warning();
  }
  unsafe extern fn callback(x: *const c_char, y: c_double) {
    // decode x
    let x = std::ffi::CStr::from_ptr(x).to_str().unwrap();
    println!("Progress feedback for {}: {}", x, y);
  }
  let process = render_prepare(&render, options.input.as_str(), callback);
  let gen = generator_generate(&generator, options.input.as_str(), options.aggressiveness.into(), options.invert, callback);
  render_render(&render, process, options.output.as_str(), gen.cuts, options.quality.into(), callback);
}

fn process_files_in_dir(options: Options, generator: Library, render: Library) {
  let files = Path::new(&options.input).read_dir().unwrap();
  // map files to paths
  let files: Vec<_> = files.map(|f| f.unwrap().path()).collect();
  let files: Vec<_> = files.into_iter().filter(|f| f.is_file()).collect();
  let files: Vec<_> = files.into_iter().filter(|f| tree_magic::from_filepath(f).starts_with("video")).collect();
  
  let reencode = options.reencode.as_str();

  for file in files {
    let file_path = file.file_name().unwrap().to_str().unwrap();
    let output_path;
    if options.output != "" {
      let tmp = Path::new(&options.output).join(&file).to_str().unwrap().to_string();
      output_path = tmp;
    } else {
      let tmp = helper::get_automatic_path(file.to_str().unwrap(), options.invert);
      output_path = tmp;
    };

    let options = Options {
      input: file_path.to_string(),
      output: output_path.to_string(),
      aggressiveness: options.aggressiveness,
      quality: options.quality,
      invert: options.invert,
      reencode: reencode.to_string(),
    };

    unsafe {
      run(options, &generator, &render);
    }
  }
}

fn process_single_file(options: Options, generator: Library, render: Library) {
  unsafe {
    run(options, &generator, &render);
  }
}

// TODO: add proper progress stuff

fn main() {
  unsafe {
    let render = load_render();
    let render_version = module_version(&render);
    let generator = load_generator();
    let generator_version = module_version(&generator);

    greetings(render_version.as_str(), generator_version.as_str());

    let mut options = parse_args();
    options = validate_args(options);

    if Path::new(options.input.as_str()).is_dir() {
      process_files_in_dir(options, generator, render);
    }
    else {
      process_single_file(options, generator, render);
    }
  }
}