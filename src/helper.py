import os
import time
from pathlib import Path
from queue import Queue
from threading import Thread

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

def read_progress(pbar, ffmpeg_run):
  """
  Read the output of a ffmpeg run and update the given progress bar.

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
        value = parts[1] if len(parts) > 1 else None # TODO: this might cause float(None):
        if key == "out_time_ms":
          time = max(round(float(value) / 1000000., 2), 0)
          pbar.update(int(time * 1000) - pbar.count)
        elif key == "progress" and value == "end":
          pbar.update(pbar.total - pbar.count)
