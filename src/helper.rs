pub fn get_automatic_path(file: &str, invert: bool) -> String {
  let mut automatic_name_insert = "_lecturecut".to_string();

  if invert {
    automatic_name_insert = "_inverted_lecturecut".to_string();
  }

  // if windows replace \ with / for now
  let file = file.replace("\\", "/");

  // split file in path and extension
  let file_stuff = file.split("/").collect::<Vec<&str>>();
  let file_path = file_stuff[0..file_stuff.len() - 1].join("/");
  let file_name = file_stuff[file_stuff.len() - 1];
  let file_name_stuff = file_name.split(".").collect::<Vec<&str>>();
  let file_name_without_extension = file_name_stuff[0..file_name_stuff.len() - 1].join(".");
  let file_extension = file_name_stuff[file_name_stuff.len() - 1];

  let new_file_name = format!("{}{}.{}", file_name_without_extension, automatic_name_insert, file_extension);

  let file = if file_path != "" {
    format!("{}/{}", file_path, new_file_name)
  } else {
    new_file_name
  };

  if cfg!(windows) {
    file.replace("/", "\\")
  } else {
    file
  }
}

pub fn make_clickable_link(text: &str, link: &str) -> String {
  format!("\u{1b}]8;;{}\u{1b}\\{}\u{1b}]8;;\u{1b}\\", link, text)
}