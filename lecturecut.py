#!/usr/bin/env python3

import argparse
import atexit
from itertools import takewhile
import cv2
import enlighten
import ffmpeg
import os
import textwrap
import time
import uuid
import vad
from joblib import Parallel, delayed
from queue import Queue
from threading import Thread
from functools import wraps
import time


TRANSCODER_PROCESSES = 12


def timing(func):
  @wraps(func)
  def timeit_wrapper(*args, **kwargs):
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    total_time = end_time - start_time
    fileName = instances[args[1]]["file"]
    data = f'{func.__name__} {fileName} took {total_time:.4f} seconds with {TRANSCODER_PROCESSES} processes.\n'
    with open('performance.log', 'a') as f:
      f.write(data)
    return result
  return timeit_wrapper


instances = {}

def reader(pipe, queue):
  try:
    with pipe:
      for line in iter(pipe.readline, b''):
        queue.put((pipe, line))
  finally:
    queue.put(None)

def delete_directory_recursively(path, retryCounter=10):
  if os.path.exists(path):
    for _ in range(retryCounter):
      try:
        for filename in os.listdir(path):
          if os.path.isdir(path + filename):
            delete_directory_recursively(path + filename + '/')
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
        parts = line.split('=')
        key = parts[0] if len(parts) > 0 else None
        value = parts[1] if len(parts) > 1 else None
        if key == 'out_time_ms':
          time = max(round(float(value) / 1000000., 2), 0)
          pbar.update(int(time * 1000) - pbar.count)
        elif key == 'progress' and value == 'end':
          pbar.update(pbar.total - pbar.count)

def init_cache(instance):
  cache_path = CACHE_PREFIX + f"/{instance}/"
  if os.path.exists(cache_path):
    raise Exception("Cache already exists")
  os.mkdir(cache_path)
  os.mkdir(cache_path + "/segments")
  os.mkdir(cache_path + "/cutSegments")

def cleanup(instance):
  cache_path = CACHE_PREFIX + f"/{instance}/"
  delete_directory_recursively(cache_path)

def generate_cut_list(instance):
  global instances
  file = instances[instance]["file"]
  instances[instance]["cuts"] = vad.run(file, aggressiveness, invert)

def prepare_video(manager, instance):
  _split_video(manager, instance)
  _analyse_segments(manager, instance)

def _split_video(manager, instance):
  cache_path = CACHE_PREFIX + f"/{instance}/"
  file = instances[instance]["file"]

  total_input_length = _get_video_length(None, file)
  bar_total = int(total_input_length * 1000)
  pbar = manager.counter(total=bar_total, desc='Segmenting ')

  split = (
    ffmpeg
    .input(file)
    .output(cache_path + 'segments/out%05d.ts',
        f='segment',
        c='copy',
        reset_timestamps=1)
    .global_args('-progress', 'pipe:1')
    .global_args('-loglevel', 'error')
    .global_args('-hide_banner')
    .global_args('-nostdin')
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  read_progress(pbar, split)
  pbar.close()

def _analyse_segments(manager, instance):
  global instances
  instances[instance]["segments"] = {}
  cache_path = CACHE_PREFIX + f"/{instance}/"
  
  segments = sorted(os.listdir(cache_path + "segments"))
  pbar = manager.counter(total=len(segments),
      desc='Analysing  ',
      unit='segments')

  durations = Parallel(n_jobs=2)(
      delayed(_get_video_length)
      (pbar, f'{cache_path}segments/{path}')
      for path in segments)
  # calculate start end map
  total_duration = 0
  for i, duration in enumerate(durations):
    instances[instance]["segments"][i] = {
      "start": total_duration,
      "end": total_duration + duration,
    }
    total_duration += duration
  pbar.close()

def _get_video_length(pbar, videoPath):
  video = cv2.VideoCapture(videoPath)
  fps = video.get(cv2.CAP_PROP_FPS)
  frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
  if pbar: pbar.update()
  return frame_count / fps

@timing
def transcode(manger, instance):
  global instances

  cache_path = CACHE_PREFIX + f"/{instance}/"
  segments = instances[instance]["segments"]
  cuts = instances[instance]["cuts"]

  pbar = manger.counter(total=len(segments),
      desc='Transcoding',
      unit='segments')

  # for i in segments:
  def _process_segment(i):
    # cats are segments that need to be kept
    segment = segments[i]
    
    # find id of first cut ending after segment start
    first_cut_id, first_cut = next((x for x in enumerate(cuts)
        if x[1][1] > segment["start"]), (-1, None))

    # skip segment if it ends before the current cut starts
    if first_cut == None or first_cut[0] >= segment["end"]:
      pbar.update()
      return

    # if completely enclosed by a cut, copy
    if first_cut[0] <= segment["start"] and first_cut[1] >= segment["end"]:
      os.rename(f"{cache_path}segments/out{i:05d}.ts",
          f"{cache_path}cutSegments/out{i:05d}.ts")
      pbar.update()
      return

    # find all cuts that start before segment end
    cuts_in_segment = list(takewhile(lambda x: x[0] < segment["end"],
        cuts[first_cut_id+1:]))
    all_cuts = [first_cut] + cuts_in_segment

    keep = []
    for cut in all_cuts:
      start = max(segment['start'], cut[0])
      end = min(segment['end'], cut[1])
      keep.append((start, end))

    # filter keep list to remove segments that are too short
    keep = [x for x in keep if x[1] - x[0] > 0.1]

    # convert keep list from global time to segment time
    keep = [(x[0] - segment['start'], x[1] - segment['start']) for x in keep]
    
    for j,trim in enumerate(keep):
      (
        ffmpeg
        .input(f'{cache_path}segments/out{i:05d}.ts')
        .output(f'{cache_path}cutSegments/out{i:05d}_{j:03d}.ts',
            f='mpegts',
            ss=trim[0],
            to=trim[1],
            acodec="copy",
            vcodec="libx264",
            preset="fast",
            crf=quality,
            reset_timestamps=1,
            force_key_frames=0)
        .global_args('-loglevel', 'error')
        .global_args('-hide_banner')
        .global_args('-nostdin')
        .run()
      )
    pbar.update()
  Parallel(n_jobs=TRANSCODER_PROCESSES, require="sharedmem")(
      delayed(_process_segment)
      (i)
      for i in segments)
  pbar.close()


def concat_segments(manager, instance):
  cache_path = f'{CACHE_PREFIX}{instance}/'
  output = instances[instance]["output"]
  with open(f'{cache_path}list.txt', 'w') as f:
    for file in sorted(os.listdir(f'{cache_path}cutSegments')):
      f.write(f"file 'cutSegments/{file}'\n")
  total_cut_length = sum([x[1] - x[0] for x in instances[instance]["cuts"]])
  bar_total = int(total_cut_length * 1000)
  pbar = manager.counter(total=bar_total, desc='Rendering  ')
  outputargs = {}
  if reencode:
    outputargs = {
      'vcodec': 'libx264',
      'preset': 'fast',
      'crf': quality,
      'acodec': 'aac',
    }
  else:
    outputargs = {
      'c': 'copy',
    }
  concat = (
    ffmpeg
    .input(f'{cache_path}list.txt', f='concat', safe=0)
    .output(output, **outputargs)
    .global_args('-progress', 'pipe:1')
    .global_args('-loglevel', 'error')
    .global_args('-hide_banner')
    .global_args('-nostdin')
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  read_progress(pbar, concat)
  pbar.close()

def run(manager, config):
  global instances

  instance = str(uuid.uuid4())
  instances[instance] = {
    "file": None,
    "output": None,
    "manager": manager,
  }
  for key in config:
    instances[instance][key] = config[key]

  file_name = os.path.basename(instances[instance]["file"])
  file_name = manager.term.orange(file_name)
  main_format = f'Cutting {file_name}{{fill}}'+\
      'Stage: {stage}{fill}{elapsed}'
  status = manager.status_bar(status_format=main_format,
                              color='bold_bright_white_on_lightslategray',
                              justify=enlighten.Justify.CENTER,
                              stage=f"[0/4] Initializing",
                              autorefresh=True,
                              min_delta=0.2)

  init_cache(instance)
  status.update(stage=f"[1/4] Preparing video")
  Parallel(n_jobs=2, require='sharedmem')([
      delayed(generate_cut_list)(instance),
      delayed(prepare_video)(manager, instance)])
  status.update(stage=f"[2/4] Transcoding video")
  transcode(manager, instance)
  status.update(stage=
      "[3/4] Rendering & Reencoding"
      if reencode else
      "[3/4] Rendering video")
  concat_segments(manager, instance)
  cleanup(instance)
  status.update(stage=f"[4/4] Done 🎉", force=True)
  status.close()

CACHE_PREFIX = "./" # needs to end with a slash

invert = False
quality = 20
aggressiveness = 3
reencode = False

def main():
  global invert, quality, aggressiveness, reencode
  parser = argparse.ArgumentParser(description=textwrap.dedent('''
    LectureCut is a tool to remove silence from videos.

    It uses WebRTC's VAD to detect silence and ffmpeg to transcode the video.
    To speed up transcoding, a form of smart encoding is employed. This means
    that the video is split into segments and only the segments that need to be
    cut are transcoded. This results in a much faster transcoding process, but
    the output video will have a slightly lower quality than the input video.
  '''))

  parser.add_argument(
      '-i', '--input',
      help='The video file to process',
      required=True)
  parser.add_argument(
      '-o', '--output',
      help='The output file. If not specified,'+\
          ' the input file will be overwritten',
      required=False)
  parser.add_argument(
      '-q', '--quality',
      help='The quality of the output video. Lower is better. Default: 20',
      required=False,
      type=int,
      default=20)
  parser.add_argument(
      '-a', '--aggressiveness',
      help='The aggressiveness of the VAD.'+\
          ' Higher is more aggressive. Default: 3',
      required=False,
      type=int,
      default=3)
  parser.add_argument(
      '-r', '--reencode',
      help='Reencode the video with a given video codec.',
      required=False,
      type=str)
  parser.add_argument(
      '--invert',
      help='Invert the selection.'+\
          ' This will cut out all segments that are not silence.',
      required=False,
      action='store_true')

  args = parser.parse_args()

  if args.invert:
    invert = True
  if args.quality:
    quality = args.quality
  if args.aggressiveness:
    aggressiveness = args.aggressiveness
  if args.reencode:
    reencode = args.reencode

  if args.invert and not args.aggressiveness:
    aggressiveness = 1

  manager = enlighten.get_manager()
  name = manager.term.link('https://github.com/Gamer92000/LectureCut',
      'LectureCut')
  author = manager.term.link('https://github.com/Gamer92000', 'Gamer92000')
  manager.status_bar(f' {name} - Made with ❤️ by {author}! ',
      position=1,
      fill='-',
      justify=enlighten.Justify.CENTER)

  automatic_name_insert = "_lecturecut."
  if invert:
    automatic_name_insert = "_inverted" + automatic_name_insert

  # if input file is a directory, process all files in it
  if os.path.isdir(args.input):
    files = sorted(os.listdir(args.input))
    files = [f for f in files if os.path.isfile(os.path.join(args.input, f))]
    files = [os.path.join(args.input, f) for f in files]
    pbar = manager.counter(total=len(files), desc='Processing ')
    get_file_path = lambda x: x
    if args.output:
      if not os.path.isdir(args.output):
        os.mkdir(args.output)
      get_file_path = lambda x: os.path.join(args.output, os.path.basename(x))
    else:
      get_file_path = lambda x: os.path.splitext(os.path.basename(x))[0] +\
          automatic_name_insert +\
          args.input.rsplit(x, 1)[1]
    for file in files:
      run(manager, {
        "file": file,
        "output": get_file_path(file)
      })
      pbar.update()

  fallback_output = args.input.rsplit(".", 1)[0] +\
      automatic_name_insert +\
      args.input.rsplit(".", 1)[1]

  run(manager, {
    "file": args.input,
    "output": args.output if args.output else fallback_output
  })
  
  manager.stop()
  print()

def shotdown_cleanup():
  print()
  print("Cleaning up after unexpected exit...")
  # sleep to make sure open file handles are closed
  time.sleep(3)
  for instance in instances:
    instances[instance]["manager"].stop()
    cachePath = f'{CACHE_PREFIX}{instance}/'
    if os.path.isdir(cachePath):
      delete_directory_recursively(cachePath)

if __name__ == "__main__":
  atexit.register(shotdown_cleanup)
  main()
  atexit.unregister(shotdown_cleanup)
