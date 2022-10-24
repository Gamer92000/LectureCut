from ctypes import c_char_p, c_double, CFUNCTYPE
import cv2
from threading import Lock

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
