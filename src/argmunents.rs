extern crate argparse;
extern crate tree_magic;

use std::path::Path;

use self::argparse::{ArgumentParser, Store};

use crate::{printer::{raise_error, print_dir_not_empty_warning, print_reencode_missing_check_warning}, helper::get_automatic_path};

#[derive(Clone)]
pub struct Options {
  pub input: String,
  pub output: String,
  pub quality: u8,
  pub aggressiveness: u8,
  pub reencode: String,
  pub invert: bool,
}

pub fn parse_args() -> Options {
  let mut options: Options = Options {
    input: String::new(),
    output: String::new(),
    quality: 20,
    aggressiveness: 1,
    reencode: String::new(),
    invert: false,
  };
  {
    let mut ap = ArgumentParser::new();
    ap.set_description("LectureCut is a tool to remove silence from videos.

It uses WebRTC's VAD to detect silence and ffmpeg to transcode the video.
To speed up transcoding, a form of smart encoding is employed. This means
that the video is split into segments and only the segments that need to be
cut are transcoded. This results in a much faster transcoding process, but
the output video will have a slightly lower quality than the input video.");
    
    ap.refer(&mut options.input)
        .add_option(&["-i", "--input"], Store,
        "The video file to process")
        .required();
    ap.refer(&mut options.output)
        .add_option(&["-o", "--output"], Store,
        "The output file. If not specified, LectureCut will automatically generate a name.");
    ap.refer(&mut options.quality)
        .add_option(&["-q", "--quality"], Store,
        "The quality of the parts of the video that need to be transcoded. Lower is better. Default: 20");
    ap.refer(&mut options.aggressiveness)
        .add_option(&["-a", "--aggressiveness"], Store,
        "The aggressiveness of the VAD. Higher is more aggressive. Default: 3");

    ap.parse_args_or_exit();
  }

  // because windows is seemingly designed by a 5 year old
  // we need to replace trailing double quotes with a backslash
  // ( see https://bugs.python.org/msg364246 )
  if cfg!(windows) {
    if options.input.ends_with("\"") {
      options.input = options.input.replace("\"", "\\");
    }
  }

  options
}


pub fn validate_args(options: Options) -> Options {
  let mut changed_options = options.clone();

  // input validation
  let input_path: &Path = Path::new(options.input.as_str());
  let input_is_file: bool = input_path.is_file();
  let input_is_dir: bool = input_path.is_dir();

  // check if input is a file or a directory (os.path.exists)
  if !input_path.exists() {
    raise_error("Input file or directory does not exist.");
  }
  if !input_is_file && !input_path.is_dir() {
    panic!("Input needs to be a file or a directory.");
  }
  // check filetype using magicbytes if file
  if input_is_file {
    let filetype: String = tree_magic::from_filepath(input_path);
    // if not video, warn user
    if !filetype.starts_with("video") {
      println!("Warning: Input file is not a video file.");
    }
  }

  // output validation
  if options.output != "" {
    // may not contain any illegal characters for paths
    // if is windows
    let mut illegal_chars: String = "".to_string();
    if cfg!(windows) {
      illegal_chars += r#"<>:"|?*"#;
      for i in 0..32 {
        illegal_chars += i.to_string().as_str();
      }
    } else {
      illegal_chars = 0.to_string();
    }
    for c in illegal_chars.chars() {
      if options.output.contains(c) {
        raise_error("Output path contains illegal characters.");
      }
    }
    let output_path: &Path = Path::new(options.output.as_str());
    if input_is_dir {
      // if input is directory, output must be directory
      if output_path.exists() {
        if !output_path.is_dir() {
          raise_error("Output path needs to be a directory.");
        }
        // if output directory exists, it must be empty
        if output_path.read_dir().unwrap().count() > 0 {
          print_dir_not_empty_warning();
        }
      }
      else {
        // try to create output directory raise_error if it fails
        if std::fs::create_dir(output_path).is_err() {
          raise_error("Could not create output directory.");
        }
      }
    } else {
      // if input is file, output must be file
      if output_path.exists() {
        raise_error("Output file already exists.")
      }
    }
  }
  else {
    if !input_is_dir {
      changed_options.output = get_automatic_path(options.input.as_str(), options.invert);
      if Path::new(changed_options.output.as_str()).exists() {
        raise_error("Output file already exists.")
      }
    }
  }

  if options.quality > 51 {
    raise_error("Quality must be between 0 and 51.");
  }

  if options.aggressiveness > 3 {
    raise_error("Aggressiveness must be between 0 and 3.");
  }

  if options.reencode != "" {
    print_reencode_missing_check_warning()
  }

  changed_options
}