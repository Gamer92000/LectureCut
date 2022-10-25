import os
import rich
from rich.align import Align
from rich.table import Table

def print_stats(files, total_time):
  """
  Print some stats for the given files.

  files -- a list of tuples of (input_file, output_file, stats)
  total_time -- the total time taken to process all files
  """
  table = Table(title="File Stats", title_style="white italic")

  table.add_column("Input File", justify="left", style="yellow")
  table.add_column("Size Changes", justify="right", style="plum4")
  table.add_column("Duration Changes", justify="right", style="cyan")
  table.add_column("Duration %", justify="right", style="magenta")

  # total length of input video 
  total_input_length = 0
  total_input_size = 0
  total_output_length = 0
  total_output_size = 0

  for input_file, output_file, stats in files:
    input_length = stats.len_pre_cut
    input_size = os.path.getsize(input_file)
    output_length = stats.len_post_cut
    output_size = os.path.getsize(output_file)
    total_input_length += input_length
    total_input_size += input_size
    total_output_length += output_length
    total_output_size += output_size
    table.add_row(
      os.path.basename(input_file),
      f"{input_size / 1024 / 1024:.2f} MB -> {output_size / 1024 / 1024:.2f} MB",
      f"{input_length / 60:.2f} min -> {output_length / 60:.2f} min",
      f"{output_length / input_length * 100:.2f} %"
    )
  
  if len(files) > 1:
    table.add_row(
      "[italic]Total",
      f"{total_input_size / 1024 / 1024:.2f} MB -> {total_output_size / 1024 / 1024:.2f} MB",
      f"{total_input_length / 60:.2f} min -> {total_output_length / 60:.2f} min",
      f"{total_output_length / total_input_length * 100:.2f} %"
    )

  performance = f"[bold green]Processed [bold cyan]{len(files)} [bold green]video{'s' if len(files) > 1 else ''} in [bold cyan]{total_time / 60:.0f} [bold green]min and [bold cyan]{total_time % 60:.0f} [bold green]sec."
  
  rich.print()
  rich.print(Align(table, align="center"))
  rich.print()
  rich.print(Align(performance, align="center"))
  rich.print()