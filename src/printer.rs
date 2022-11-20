extern crate console;
extern crate tabled;

use std::path::Path;
use std::time::Duration;

use self::tabled::object::Cell;

use self::tabled::format::Format;

use self::tabled::ModifyObject;

use self::tabled::object::Object;

use self::tabled::object::Columns;
use self::tabled::object::Rows;

use self::tabled::Alignment;
use self::tabled::Style;

use self::tabled::builder::Builder;

use self::console::measure_text_width;
use self::console::pad_str;

use crate::helper::make_clickable_link;
use crate::module_manager::GeneratorStats;

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
  let l7 = l7_left + &" ".repeat(50 - l7_right_width) + &l7_right;

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
    term.write_line("").unwrap();
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

pub fn print_stats(files: Vec<(String, String, GeneratorStats)>, time_used: Duration) {
  let mut builder = Builder::default();

  builder.set_columns([
    "Input File",
    "Size Changes",
    "Duration Changes",
    "Duration %",
  ]);

  let mut total_input_length = 0.0;
  let mut total_input_size = 0.0;
  let mut total_output_length = 0.0;
  let mut total_output_size = 0.0;

  for (input_file, output_file, stats) in &files {
    let input_length = stats.len_pre_cut;
    let input_size = Path::new(input_file.as_str()).metadata().unwrap().len() as f64 / 1024.0 / 1024.0;
    let output_length = stats.len_post_cut;
    let output_size = Path::new(output_file.as_str()).metadata().unwrap().len() as f64 / 1024.0 / 1024.0;

    let size_change_str = format!("{:.2} MB -> {:.2} MB", input_size, output_size);

    let duration_change_str = format!("{} min {} sec -> {} min {} sec", (input_length / 60.0) as i8, (input_length % 60.0) as i8, (output_length / 60.0) as i8, (output_length % 60.0)as i8);

    let length_change_percent_str = format!("{:.2} %", (output_length / input_length) * 100.0);

    let intput_file_str = input_file.as_str();
    intput_file_str.to_string().truncate(20);

    builder.add_record([
      intput_file_str.to_string(),
      size_change_str,
      duration_change_str,
      length_change_percent_str,
    ]);

    total_input_length += input_length;
    total_input_size += input_size;
    total_output_length += output_length;
    total_output_size += output_size;
  }

  let total_size_change_str = format!("{:.2} MB -> {:.2} MB", total_input_size, total_output_size);
  let total_duration_change_str = format!("{} min {} sec -> {} min {} sec", (total_input_length / 60.0) as i8, (total_input_length % 60.0) as i8, (total_output_length / 60.0) as i8, (total_output_length % 60.0)as i8);
  let total_length_change_percent_str = format!("{:.2} %", (total_output_length / total_input_length) * 100.0);

  if files.len() > 1 {
    builder.add_record([
      "Total".to_string(),
      total_size_change_str,
      total_duration_change_str,
      total_length_change_percent_str,
    ]);
  }

  // align columns left, right, right, right

  let mut binding = builder.build();
  let mut table = binding
    .with(Style::rounded())
    .with(Rows::single(0).modify().with(Alignment::center()))
    .with(Rows::new(1..).not(Columns::first()).modify().with(Alignment::right()))
    .with(Columns::single(0).modify().with(Format::new(|s| style(s).yellow().to_string())))
    .with(Columns::single(1).modify().with(Format::new(|s| style(s).fg(console::Color::Color256(96)).to_string())))
    .with(Columns::single(2).modify().with(Format::new(|s| style(s).cyan().to_string())))
    .with(Columns::single(3).modify().with(Format::new(|s| style(s).magenta().to_string())))
    .with(Rows::single(0).modify().with(Format::new(|s| style(s).bold().to_string())));
    
  if files.len() > 1 {
    table = table.with(Cell(files.len() + 1, 0).modify().with(Format::new(|s| style(s).italic().white().to_string())))
  }

  let table = table.to_string();

  // align table center

  let term_width = Term::stdout().size().1;
  for line in table.lines() {
    let line = line.trim();
    let padded = pad_str(line, term_width.into(), console::Alignment::Center, None);
    println!("{}", padded);
  }

  // Processed x files in y min and z sec
  let ts1 = style("Processed ").bold().green();
  let ts2 = style(files.len().to_string()).bold().cyan();
  let ts3 = style(" files in ").bold().green();
  let ts4 = style(format!("{}", time_used.as_secs() / 60)).bold().cyan();
  let ts5 = style(" min and ").bold().green();
  let ts6 = style(format!("{}", time_used.as_secs() % 60)).bold().cyan();
  let ts7 = style(" seconds.").bold().green();

  let ts = format!("{}{}{}{}{}{}{}", ts1, ts2, ts3, ts4, ts5, ts6, ts7);

  let ts = pad_str(ts.as_str(), term_width.into(), console::Alignment::Center, None);
  let term = Term::stdout();
  term.write_line("").unwrap();
  term.write_line(&ts).unwrap();
  term.write_line("").unwrap();
}