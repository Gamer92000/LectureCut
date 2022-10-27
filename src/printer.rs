extern crate console;

use self::console::measure_text_width;
use self::console::pad_str;

use crate::helper::make_clickable_link;

use self::console::Term;
use self::console::style;

pub fn greetings(render_version: &str, generator_version: &str) {
  let term = Term::stdout();

  term.write_line("").unwrap();

  // align text to center
  let mut lines = Vec::new();

  lines.push("██╗    ███████╗ ██████╗████████╗██╗   ██╗███████╗███████╗    ██████╗██╗  ██╗████████╗");
  lines.push("██║    ██╔════╝██╔════╝╚══██╔══╝██║   ██║██╔══██║██╔════╝   ██╔════╝██║  ██║╚══██╔══╝");
  lines.push("██║    █████╗  ██║        ██║   ██║   ██║██████╔╝█████╗     ██║     ██║  ██║   ██║   ");
  lines.push("██║    ██╔══╝  ██║        ██║   ██║   ██║██╔══██╗██╔══╝     ██║     ██║  ██║   ██║   ");
  lines.push("██████╗███████╗╚██████╗   ██║   ╚██████╔╝██║  ██║███████╗   ╚██████╗╚█████╔╝   ██║   ");
  lines.push("╚═════╝╚══════╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝    ╚═════╝ ╚════╝    ╚═╝   ");
  
  let l7_left = make_clickable_link("Source", "https://github.com/Gamer92000/LectureCut/") + " - Made with ❤️ by " + &make_clickable_link("Gamer92000", "https://github.com/Gamer92000");
  let l7_right = format!("Generator: {} | Render: {}", style(render_version).yellow(), style(generator_version).yellow());
  let l7_right_width = measure_text_width(l7_right.as_str());
  let l7 = l7_left + &" ".repeat(51 - l7_right_width) + &l7_right;

  // center text
  let term_width = term.size().1;

  for line in lines {
    let padded = pad_str(line, term_width.into(), console::Alignment::Center, None);
    term.write_line(&padded).unwrap();
  }
  
  // manually center l7, because console does not support links...
  let padding = term.size().1 - 86;
  let l7_padded = " ".repeat((padding / 2).into()) + &l7;
  term.write_line(&l7_padded).unwrap();

  term.write_line("").unwrap();
}


pub fn raise_error(message: &str) {
    let term = Term::stderr();
    term.write_line(&format!("{}: {}", style("Error").red(), message)).unwrap();
    std::process::exit(1);
}

pub fn print_non_mp4_warning() {
    let term = Term::stderr();
    term.write_line(&format!("{}: {}", style("⚠️").yellow(), "The input file is not an MP4 file. This may cause issues.")).unwrap();
}

pub fn print_dir_not_empty_warning() {
    let term = Term::stderr();
    term.write_line(&format!("{}: {}", style("⚠️").yellow(), "The output directory is not empty. Existing files will be skipped.")).unwrap();
}

pub fn print_reencode_missing_check_warning() {
    let term = Term::stderr();
    term.write_line(&format!("{}: {}", style("⚠️").yellow(), "The reencode value is currently not checked. This may result in unpredictable behavior.")).unwrap();
}