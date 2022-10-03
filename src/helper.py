import os
from pathlib import Path
import time
from queue import Queue
from threading import Thread

# TODO: replace with shutil.rmtree
def delete_directory_recursively(path, retryCounter=10):
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
  try:
    with pipe:
      for line in iter(pipe.readline, b""):
        queue.put((pipe, line))
  finally:
    queue.put(None)

def read_progress(pbar, ffmpeg_run):
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
          pbar.update(int(time * 1000) - pbar.count)
        elif key == "progress" and value == "end":
          pbar.update(pbar.total - pbar.count)
