from ctypes import c_char_p, c_double, CFUNCTYPE
import cv2
from threading import Lock
import rich


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