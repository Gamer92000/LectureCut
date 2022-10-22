import os
import time
from pathlib import Path
from queue import Queue
from threading import Thread
import cv2


def get_video_length(videoPath, progress=None, pbar=None):
  """
  Get the length of the given video in seconds.

  progress -- the manager for the progress bars
  pbar -- the progress bar
  videoPath -- the path to the video
  """
  video = cv2.VideoCapture(videoPath)
  fps = video.get(cv2.CAP_PROP_FPS)
  frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
  if pbar: progress.update(pbar, advance=1)
  return frame_count / fps


# TODO: replace with shutil.rmtree
def delete_directory_recursively(path, retryCounter=10):
  """
  Delete a directory and all its contents.

  path -- The path to the directory to delete.
  retryCounter -- The number of times to retry deleting the directory.
  """
  if os.path.exists(path):
    for _ in range(retryCounter):
      try:
        for filename in os.listdir(path):
          if os.path.isdir(path + filename):
            delete_directory_recursively(path + filename + "/")
          else:
            for _ in range(retryCounter):
              try:
                os.remove(path + filename)
                break
              except:
                time.sleep(0.1)
        os.rmdir(path)
        break
      except:
        time.sleep(0.1)

def reader(pipe, queue):
  """
  Read the output of a pipe and put it in a queue.

  pipe -- The pipe to read from.
  queue -- The queue to put the output in.
  """
  try:
    with pipe:
      for line in iter(pipe.readline, b""):
        queue.put((pipe, line))
  finally:
    queue.put(None)

def read_progress(progress, pbar, ffmpeg_run):
  """
  Read the output of a ffmpeg run and update the given progress bar.

  progress -- The manager that controls the progress bars.
  pbar -- The progress bar to update.
  ffmpeg_run -- The ffmpeg run to read the output from.
  """
  q = Queue()
  Thread(target=reader, args=(ffmpeg_run.stdout, q)).start()
  Thread(target=reader, args=(ffmpeg_run.stderr, q)).start()
  for _ in range(2):
    for source, line in iter(q.get, None):
      line = line.decode()
      if source == ffmpeg_run.stderr:
        print(line)
      else:
        line = line.rstrip()
        parts = line.split("=")
        key = parts[0] if len(parts) > 0 else None
        value = parts[1] if len(parts) > 1 else None # TODO: this might cause float(none):
        if key == "out_time_ms":
          time = max(round(float(value) / 1000000., 2), 0)
          progress.update(pbar, advance=int(time * 1000))
        elif key == "progress" and value == "end":
          progress.update(pbar, completet=True)
