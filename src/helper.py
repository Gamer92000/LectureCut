from ctypes import CFUNCTYPE, WINFUNCTYPE, c_char_p, c_double
import cv2
import os

FUNCTYPE = WINFUNCTYPE if os.name == "nt" else CFUNCTYPE

def get_video_length(videoPath):
  """
  Get the length of the given video in seconds.

  progress -- the manager for the progress bars
  pbar -- the progress bar
  videoPath -- the path to the video
  """
  video = cv2.VideoCapture(videoPath)
  fps = video.get(cv2.CAP_PROP_FPS)
  frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
  return frame_count / fps


def get_progress_callback(progress, ptypes):
  """
  Generate a c callback to get progress updates.

  progress -- the manager for the progress bars
  ptypes -- a map of existing progress types
  """
  @FUNCTYPE(None, c_char_p, c_double)
  def progress_callback(ptype, delta):
    if ptype not in ptypes:
      ptypes[ptype] = progress.add_task(str(ptype, "utf-8"), total=100)
    progress.update(ptypes[ptype], advance=delta)

  return progress_callback
