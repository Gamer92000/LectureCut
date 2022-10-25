import rich
from rich.align import Align

def greetings(render_version, generator_version):
  """
  Create a manager for the progress bars.

  render_version -- the version of the render module
  generator_version -- the version of the generator module
  """

  title = "██╗    ███████╗ ██████╗████████╗██╗   ██╗███████╗███████╗    ██████╗██╗  ██╗████████╗\n" + \
          "██║    ██╔════╝██╔════╝╚══██╔══╝██║   ██║██╔══██║██╔════╝   ██╔════╝██║  ██║╚══██╔══╝\n" + \
          "██║    █████╗  ██║        ██║   ██║   ██║██████╔╝█████╗     ██║     ██║  ██║   ██║\n" + \
          "██║    ██╔══╝  ██║        ██║   ██║   ██║██╔══██╗██╔══╝     ██║     ██║  ██║   ██║\n" + \
          "██████╗███████╗╚██████╗   ██║   ╚██████╔╝██║  ██║███████╗   ╚██████╗╚█████╔╝   ██║\n" + \
          "╚═════╝╚══════╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝    ╚═════╝ ╚════╝    ╚═╝"
  rich.print()
  title = Align(title, align="center")
  rich.print(title)
  subtitle = "[link=https://github.com/Gamer92000/LectureCut]Source Code[/link] - Made with ❤️ by [link=https://github.com/Gamer92000]Gamer92000[/link]"
  render_version = f"Render [yellow]{render_version}[/yellow]"
  generator_version = f"Generator [yellow]{generator_version}[/yellow]"
  version = f"{render_version} | {generator_version}"
  version = version.rjust(79)
  subtitle = f"{subtitle}{version}"
  subtitle = Align(subtitle, align="center")
  rich.print(subtitle)

def print_non_mp4_warning():
  """
  Print a warning if an input file is not an mp4.
  """
  rich.print("[yellow]⚠️: The input file is not an mp4. This may cause issues.[/yellow]")

def print_dir_not_empty_warning():
  """
  Print a warning if the output directory is not empty.
  """
  rich.print("[yellow]⚠️: The output directory is not empty. Existing files will be skipped.[/yellow]")

def print_reencode_missing_check_warning():
  """
  Print a warning if the reencode check is missing.
  """
  rich.print("[yellow]⚠️: The reencode value is currently not checked. This may result in unpredictable behavior.[/yellow]")

def raise_rich(message):
  """
  Raise a rich error.

  message -- the error message
  """
  rich.print(f"[red]ERROR[/red]: {message}")
  rich.print()
  raise SystemExit(1)