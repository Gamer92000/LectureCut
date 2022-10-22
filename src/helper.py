import os
import time
import cv2


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