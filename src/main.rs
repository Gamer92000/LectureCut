extern crate libloading;
extern crate console;
extern crate indicatif;

mod argmunents;
mod printer;
mod helper;
mod module_manager;

use std::path::Path;
use std::sync::Mutex;

use argmunents::{parse_args, validate_args, Options};
use indicatif::ProgressBar;
use indicatif::ProgressStyle;
use module_manager::GeneratorStats;
use printer::print_stats;
use self::indicatif::MultiProgress;
use self::console::style;
use crate::module_manager::generator_generate;
use crate::module_manager::render_render;

use self::libloading::Library;
use module_manager::{load_render, load_generator, module_version, render_prepare};
use printer::{greetings, print_non_mp4_warning};

use std::ffi::c_char;
use std::ffi::c_double;

struct ProgressWrapper {
  pub progress: Option<MultiProgress>,
  pub pbars: Vec<(String, ProgressBar)>,
}

static PROG_WRAPPER: Mutex<ProgressWrapper> = Mutex::new(ProgressWrapper {
  progress: Option::None,
  pbars: Vec::new(),
});



fn run(options: &Options, generator: &Library, render: &Library) -> GeneratorStats  {
  let locked_prog = PROG_WRAPPER.lock().unwrap();

  locked_prog.progress.as_ref().unwrap().println((format!(" Input: {}", style(&options.input).yellow())).to_string()).unwrap();
  locked_prog.progress.as_ref().unwrap().println((format!("Output: {}", style(&options.output).yellow())).to_string()).unwrap();
  locked_prog.progress.as_ref().unwrap().println("".to_string()).unwrap();

  drop(locked_prog);

  if tree_magic::from_filepath(Path::new(options.input.as_str())) != "video/mp4" {
    print_non_mp4_warning();
  }

  unsafe extern fn callback(name: *const c_char, advance: c_double) {
    // decode name
    let name = std::ffi::CStr::from_ptr(name).to_str().unwrap();
    // lock progress.mutex
    let mut locked_prog = PROG_WRAPPER.lock().unwrap();

    // find progress bar
    let mut found = false;
    for (n, pb) in locked_prog.pbars.iter() {
      if n == name {
        // get current progress
        let current = pb.position() as f64;
        // calculate new progress
        let new = if advance == -1.0 {1000.0} else {current + (advance * 10.0)};
        pb.set_position(new as u64);
        found = true;
        break;
      }
    }
    // if not found, create new progress bar
    if !found {
      let pb = locked_prog.progress.as_ref().unwrap().add(ProgressBar::new(1000));
      pb.set_style(
        ProgressStyle::with_template("{spinner:.green} {msg} {bar:40.green/magenta} {percent:>3} % • {elapsed_precise:.yellow} • {eta_precise:.cyan}").unwrap()
        .progress_chars("━╸━")
      );
      pb.set_position((advance * 10.0) as u64);
      let padded_name = format!("{: >12}", name);
      pb.set_message(padded_name);
      locked_prog.pbars.push((name.to_string(), pb));
    }
    
    drop(locked_prog);
  }

  let process = render_prepare(&render, options.input.as_str(), callback);
  let gen = generator_generate(&generator, options.input.as_str(), options.aggressiveness.into(), options.invert, callback);
  render_render(&render, process, options.output.as_str(), gen.cuts, options.quality.into(), callback);

  let mut locked_prog = PROG_WRAPPER.lock().unwrap();
  for (_, pb) in locked_prog.pbars.iter() {
    pb.finish_and_clear();
    locked_prog.progress.as_ref().unwrap().remove(pb);
  }
  locked_prog.pbars.clear();
  drop(locked_prog);

  gen.stats
}

fn process_files_in_dir(options: Options, generator: Library, render: Library) {
  let files = Path::new(&options.input).read_dir().unwrap();
  // map files to paths
  let files: Vec<_> = files.map(|f| f.unwrap().path()).collect();
  let files: Vec<_> = files.into_iter().filter(|f| f.is_file()).collect();
  let files: Vec<_> = files.into_iter().filter(|f| tree_magic::from_filepath(f).starts_with("video")).collect();
  
  let reencode = options.reencode.as_str();

  for file in files {
    let file_path = file.to_str().unwrap();
    let output_path;

    if options.output != "" {
      let tmp = Path::new(&options.output).join(&file.file_name().unwrap()).to_str().unwrap().to_string();
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

    run(&options, &generator, &render);
  }
}

fn process_single_file(options: Options, generator: Library, render: Library) {
  // start timer
  let start = std::time::Instant::now();
  let stats = run(&options, &generator, &render);
  // stop timer
  let end = std::time::Instant::now();
  print_stats([(options.input, options.output, stats)].to_vec(), end - start);
}

fn main() {
  // initialize progress bar
  let progress = MultiProgress::new();
  let mut locked_prog = PROG_WRAPPER.lock().unwrap();
  locked_prog.progress = Some(progress.clone());
  // unlock progress bar
  drop(locked_prog);

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