#!/usr/bin/env python3

from helper import delete_directory_recursively, read_progress
from itertools import takewhile
from joblib import Parallel, delayed
from pathlib import Path
import argparse
import atexit
import cv2
import enlighten
import ffmpeg
import multiprocessing
import os
import textwrap
import time
import uuid
import vad

N_CORES = multiprocessing.cpu_count()
PROCESSES = N_CORES // 4

CACHE_PREFIX = Path("cache")

instances = {}

def init_cache(instance):
  """
  Create a cache directory for the given instance.
  The cache directory is used to store temporary files.

  instance -- the instance id
  """
  cache_path = CACHE_PREFIX / instance
  if os.path.exists(cache_path):
    raise Exception("Cache already exists")
  os.mkdir(cache_path) # TODO: use https://stackoverflow.com/a/600612, create parents
  os.mkdir(cache_path / "segments")
  os.mkdir(cache_path / "cutSegments")

def cleanup(instance):
  """
  Delete the cache directory for the given instance.

  instance -- the instance id
  """
  cache_path = CACHE_PREFIX / instance
  delete_directory_recursively(cache_path)

def generate_cut_list(instance):
  """
  Generate a list of segments that should not be cut out of the video.
  The list is stored in the instances dictionary.

  instance -- the instance id
  """
  global instances
  file = instances[instance]["file"]
  instances[instance]["cuts"] = vad.run(file, aggressiveness, invert)

def prepare_video(manager, instance):
  """
  Prepare the video for cutting.
  This includes segmenting the video and analysing the segments.

  manager -- the manager for the progress bars
  instance -- the instance id
  """
  _split_video(manager, instance)
  _analyse_segments(manager, instance)

def _split_video(manager, instance):
  """
  Split the video into segments based on keyframes.

  manager -- the manager for the progress bars
  instance -- the instance id
  """
  cache_path = CACHE_PREFIX / instance
  file = instances[instance]["file"]

  total_input_length = _get_video_length(None, file)
  bar_total = int(total_input_length * 1000)
  pbar = manager.counter(total=bar_total, desc="Segmenting ")

  split = (
    ffmpeg
    .input(file)
    .output(str(cache_path / "segments" / "out%05d.ts"),
        f="segment",
        c="copy",
        reset_timestamps=1)
    .global_args("-progress", "pipe:1")
    .global_args("-loglevel", "error")
    .global_args("-hide_banner")
    .global_args("-nostdin")
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  read_progress(pbar, split)
  pbar.close()

def _analyse_segments(manager, instance):
  """
  Analyse the length of each segment of the video.

  manager -- the manager for the progress bars
  instance -- the instance id
  """
  global instances
  instances[instance]["segments"] = {}
  cache_path = CACHE_PREFIX / instance

  segments = sorted(os.listdir(cache_path / "segments"))
  pbar = manager.counter(total=len(segments),
      desc="Analysing  ",
      unit="segments")

  durations = Parallel(n_jobs=PROCESSES)(
      delayed(_get_video_length)
      (pbar, str(cache_path / "segments" / path))
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
  """
  Get the length of the given video in seconds.

  pbar -- the progress bar
  videoPath -- the path to the video
  """
  video = cv2.VideoCapture(videoPath)
  fps = video.get(cv2.CAP_PROP_FPS)
  frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
  if pbar: pbar.update()
  return frame_count / fps

def transcode(manger, instance):
  """
  Transcode the video.

  manager -- the manager for the progress bars
  instance -- the instance id
  """
  global instances

  cache_path = CACHE_PREFIX / instance
  segments = instances[instance]["segments"]
  cuts = instances[instance]["cuts"]

  pbar = manger.counter(total=len(segments),
      desc="Transcoding",
      unit="segments")

  def _process_segment(i):
    """
    Process a single segment.

    i -- the segment number
    """
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
      os.rename(str(cache_path / "segments" / f"out{i:05d}.ts"),
          str(cache_path / "cutSegments" / f"out{i:05d}.ts"))
      pbar.update()
      return

    # find all cuts that start before segment end
    cuts_in_segment = list(takewhile(lambda x: x[0] < segment["end"],
        cuts[first_cut_id+1:]))
    all_cuts = [first_cut] + cuts_in_segment

    keep = []
    for cut in all_cuts:
      start = max(segment["start"], cut[0])
      end = min(segment["end"], cut[1])
      keep.append((start, end))

    # filter keep list to remove segments that are too short
    keep = [x for x in keep if x[1] - x[0] > 0.1]

    # convert keep list from global time to segment time
    keep = [(x[0] - segment["start"], x[1] - segment["start"]) for x in keep]

    for j,trim in enumerate(keep):
      # only transcode when a new keyframe needs to be calculated
      # otherwise just cut P and B frames
      # TODO: check if this results in a quality loss
      #       assuming that a P frame that is kept referenced a B frame
      #       that was cut, might result in the P frame losing its reference
      #       and thus (to me) unknown behaviour
      if (trim[0] == 0):
        (
          ffmpeg
            .input(str(cache_path / "segments" / f"out{i:05d}.ts"))
            .output(str(cache_path / "cutSegments" / f"out{i:05d}_{j:03d}.ts"),
              f="mpegts",
              to=round(trim[1], 5),
              codec="copy")
          .global_args("-loglevel", "error")
          .global_args("-hide_banner")
          .global_args("-nostdin")
          .run()
        )
      else:
        (
          ffmpeg
            .input(str(cache_path / "segments" / f"out{i:05d}.ts"))
            .output(str(cache_path / "cutSegments" / f"out{i:05d}_{j:03d}.ts"),
              f="mpegts",
              ss=round(trim[0], 5),
              to=round(trim[1], 5),
              acodec="copy",
              vcodec="libx264",
              preset="fast",
              crf=quality,
              reset_timestamps=1,
              force_key_frames=0)
          .global_args("-loglevel", "error")
          .global_args("-hide_banner")
          .global_args("-nostdin")
          .run()
        )
    pbar.update()
  Parallel(n_jobs=PROCESSES, require="sharedmem")(
      delayed(_process_segment)
      (i)
      for i in segments)
  pbar.close()


def concat_segments(manager, instance):
  """
  Concatenate the segments into a single video.

  manager -- the manager for the progress bars
  instance -- the instance id
  """
  cache_path = CACHE_PREFIX / instance
  output = instances[instance]["output"]
  with open(str(cache_path / "list.txt"), "w") as f:
    for file in sorted(os.listdir(str(cache_path / "cutSegments"))):
      f.write(f"file 'cutSegments/{file}'\n")
  total_cut_length = sum([x[1] - x[0] for x in instances[instance]["cuts"]])
  bar_total = int(total_cut_length * 1000)
  pbar = manager.counter(total=bar_total, desc="Rendering  ")
  outputargs = {}
  if reencode:
    outputargs = {
      "vcodec": "libx264",
      "preset": "fast",
      "crf": quality,
      "acodec": "aac",
    }
  else:
    outputargs = {
      "c": "copy",
    }
  concat = (
    ffmpeg
    .input(str(cache_path / "list.txt"), f="concat", safe=0)
    .output(output, **outputargs)
    .global_args("-progress", "pipe:1")
    .global_args("-loglevel", "error")
    .global_args("-hide_banner")
    .global_args("-nostdin")
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  read_progress(pbar, concat)
  pbar.close()

def run(manager, config):
  """
  Run the program on a single instance.

  manager -- the manager for the progress bars
  config -- the config for the instance
  """
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
  main_format = f"Cutting {file_name}{{fill}}"+\
      "Stage: {stage}{fill}{elapsed}"
  status = manager.status_bar(status_format=main_format,
                              color="bold_bright_white_on_lightslategray",
                              justify=enlighten.Justify.CENTER,
                              stage=f"[0/4] Initializing",
                              autorefresh=True,
                              min_delta=0.2)

  init_cache(instance)
  status.update(stage=f"[1/4] Preparing video")
  Parallel(n_jobs=2, require="sharedmem")([
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

invert = False
quality = 20
aggressiveness = 3
reencode = False

def parse_args():
  """
  Parse the command line arguments.
  """
  global invert, quality, aggressiveness, reencode
  parser = argparse.ArgumentParser(description=textwrap.dedent("""
    LectureCut is a tool to remove silence from videos.

    It uses WebRTC's VAD to detect silence and ffmpeg to transcode the video.
    To speed up transcoding, a form of smart encoding is employed. This means
    that the video is split into segments and only the segments that need to be
    cut are transcoded. This results in a much faster transcoding process, but
    the output video will have a slightly lower quality than the input video.
  """))

  parser.add_argument(
      "-i", "--input",
      help="The video file to process",
      required=True)
  parser.add_argument(
      "-o", "--output",
      help="The output file. If not specified,"+\
          " the input file will be overwritten",
      required=False)
  parser.add_argument(
      "-q", "--quality",
      help="The quality of the output video. Lower is better. Default: 20",
      required=False,
      type=int,
      default=20)
  parser.add_argument(
      "-a", "--aggressiveness",
      help="The aggressiveness of the VAD."+\
          " Higher is more aggressive. Default: 3",
      required=False,
      type=int,
      default=3)
  parser.add_argument(
      "-r", "--reencode",
      help="Reencode the video with a given video codec.",
      required=False,
      type=str)
  parser.add_argument(
      "--invert",
      help="Invert the selection."+\
          " This will cut out all segments that are not silence.",
      required=False,
      action="store_true")

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

  return args

def create_manager():
  """
  Create a manager for the progress bars.
  """
  manager = enlighten.get_manager()
  name = manager.term.link("https://github.com/Gamer92000/LectureCut",
      "LectureCut")
  author = manager.term.link("https://github.com/Gamer92000", "Gamer92000")
  manager.status_bar(f" {name} - Made with ❤️ by {author}! ",
      position=1,
      fill="-",
      justify=enlighten.Justify.CENTER)
  return manager

def get_automatic_name_insert():
  """
  Get the automatic name insert for the output file.
  """
  automatic_name_insert = "_lecturecut."

  if invert:
    automatic_name_insert = "_inverted" + automatic_name_insert

  return automatic_name_insert

def process_files_in_dir(args, manager):
    files = sorted(os.listdir(args.input))
    files = [f for f in files if os.path.isfile(os.path.join(args.input, f))]
    files = [os.path.join(args.input, f) for f in files]
    pbar = manager.counter(total=len(files), desc="Processing ")
    get_file_path = lambda x: x
    if args.output:
      if not os.path.isdir(args.output):
        os.mkdir(args.output)
      get_file_path = lambda x: os.path.join(args.output, os.path.basename(x))
    else:
      get_file_path = lambda x: os.path.splitext(os.path.basename(x))[0] +\
          get_automatic_name_insert() +\
          x.rsplit(".", 1)[1]
    for file in files:
      run(manager, {
        "file": file,
        "output": get_file_path(file)
      })
      pbar.update()

def main():
  """
  Main function.
  """
  args = parse_args()
  manager = create_manager()

  if os.path.isdir(args.input):
    process_files_in_dir(args, manager)

  fallback_output = args.input.rsplit(".", 1)[0] +\
      get_automatic_name_insert() +\
      args.input.rsplit(".", 1)[1]

  run(manager, {
    "file": args.input,
    "output": args.output if args.output else fallback_output
  })

  manager.stop()
  print()

def shotdown_cleanup():
  """
  Cleanup function that is called when the program is terminated.
  """
  print()
  print("Cleaning up after unexpected exit...")
  # sleep to make sure open file handles are closed
  time.sleep(3)
  for instance in instances:
    instances[instance]["manager"].stop()
    cachePath = str(CACHE_PREFIX / instance)
    if os.path.isdir(cachePath):
      delete_directory_recursively(cachePath)

if __name__ == "__main__":
  atexit.register(shotdown_cleanup)
  main()
  atexit.unregister(shotdown_cleanup)
