from ctypes import c_char_p, c_double, CFUNCTYPE
from threading import Lock
import os
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)


def get_progress_callback(progress, ptypes):
  """
  Generate a c callback to get progress updates.

  progress -- the manager for the progress bars
  ptypes -- a map of existing progress types
  """
  progress.mutex = Lock()

  @CFUNCTYPE(None, c_char_p, c_double)
  def progress_callback(ptype, delta):
    progress.mutex.acquire()
    if ptype not in ptypes:
      ptypes[ptype] = progress.add_task(str(ptype, "utf-8"), total=100)
    progress.mutex.release()
    if delta == -1:
      # set the progress to 100%
      progress.update(ptypes[ptype], completed=100)
      return
    progress.update(ptypes[ptype], advance=delta)

  return progress_callback


def get_automatic_path(file_path, invert):
  """
  Get the automatic name insert for the output file.

  file_path -- the path to the input file
  invert -- whether the cuts should be inverted
  """
  automatic_name_insert = "_lecturecut"

  if invert:
    automatic_name_insert = "_inverted" + automatic_name_insert

  name, ext = os.path.splitext(file_path)

  return name + automatic_name_insert + ext


def generate_progress_instance():
  """
  Generate a progress instance for all progress bars on a single file.
  """
  return Progress(
    TextColumn("{task.description}", justify="right"),
    BarColumn(bar_width=None),
    TextColumn("[progress.percentage]{task.percentage:>3.1f}%", justify="right"),
    "•",
    TimeRemainingColumn(),
    "•",
    TimeElapsedColumn(),
    transient=True,
  )