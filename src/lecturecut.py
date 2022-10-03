#!/usr/bin/env python3

from helper import read_progress
from itertools import takewhile
from joblib import Parallel, delayed
from pathlib import Path
from shutil import rmtree
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

def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def init_cache(instance):
  """
  Create a cache directory for the given instance.
  The cache directory is used to store temporary files.

  instance -- the instance id
  """
  cache_path = CACHE_PREFIX / instance
  if os.path.exists(cache_path):
    raise Exception("Cache already exists")
  mkdir(cache_path / "segments")
  mkdir(cache_path / "cutSegments")

def cleanup(instance):
  """
  Delete the cache directory for the given instance.

  instance -- the instance id
  """
  cache_path = CACHE_PREFIX / instance
  rmtree(cache_path)

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
  
  segments = sorted((cache_path / "segments").iterdir())
  pbar = manager.counter(total=len(segments),
      desc="Analysing  ",
      unit="segments")

  jobs = (
    delayed(_get_video_length)(pbar, str(path))
    for path in segments
  )
  durations = Parallel(n_jobs=PROCESSES)(jobs)
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

  def _process_segment(index, segment):
    """
    Process a single segment.

    index -- the segment number
    segment -- the segment
    """

    # find id of first cut ending after segment start
    first_cut_id, first_cut = next((x for x in enumerate(cuts)
        if x[1][1] > segment["start"]), (-1, None))

    # skip segment if it ends before the current cut starts
    if first_cut == None or first_cut[0] >= segment["end"]:
      pbar.update()
      return

    # if completely enclosed by a cut, copy
    if first_cut[0] <= segment["start"] and first_cut[1] >= segment["end"]:
      file_name = f"out{index:05d}.ts"
      os.rename(cache_path / "segments" / file_name,
          cache_path / "cutSegments" / file_name)
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
            .input(str(cache_path / "segments" / f"out{index:05d}.ts"))
            .output(str(cache_path / "cutSegments" / f"out{index:05d}_{j:03d}.ts"),
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
            .input(str(cache_path / "segments" / f"out{index:05d}.ts"))
            .output(str(cache_path / "cutSegments" / f"out{index:05d}_{j:03d}.ts"),
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
  jobs = (
    delayed(_process_segment)(name, segment)
    for name, segment in segments.items()
  )
  Parallel(n_jobs=PROCESSES, require="sharedmem")(jobs)
  pbar.close()


def concat_segments(manager, instance):
  """
  Concatenate the segments into a single video.

  manager -- the manager for the progress bars
  instance -- the instance id
  """
  cache_path = CACHE_PREFIX / instance
  output = instances[instance]["output"]

  batch_file = cache_path / "list.txt"
  with batch_file.open("w") as f:
    files = sorted((cache_path / "cutSegments").iterdir())
    for file in files:
      f.write(f"file '{file}'\n")

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
    .input(str(batch_file), f="concat", safe=0)
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
  Parallel(n_jobs=2, require="sharedmem")([ # TODO: keep reference to child progresses so they can be killed on shutdown cleanup
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

def process_files_in_dir(input_path, args, manager):
    files = sorted(input_path.iterdir())
    files = list(filter(lambda f: f.is_file(), files))
    pbar = manager.counter(total=len(files), desc="Processing ")
    get_file_path = lambda x: x
    if args.output:
      output_path = Path(args.output)
      if not output_path.is_dir():
        mkdir(args.output)
      get_file_path = lambda x: args.output / x.name
    else:
      get_file_path = lambda x: (x.stem + get_automatic_name_insert() + x.suffix)
    for file in files:
      run(manager, {
        "file": str(file),
        "output": str(get_file_path(file))
      })
      pbar.update()

def main():
  """
  Main function.
  """
  args = parse_args()
  manager = create_manager()

  input_path = Path(args.input)

  if input_path.is_dir():
    process_files_in_dir(input_path, args, manager)

  fallback_output = input_path.stem + get_automatic_name_insert() + input_path.suffix

  run(manager, {
    "file": str(args.input),
    "output": str(args.output if args.output else fallback_output)
  })

  manager.stop()
  print()

def shutdown_cleanup():
  """
  Cleanup function that is called when the program is terminated.
  """
  print()
  print("Cleaning up after unexpected exit...")
  # sleep to make sure open file handles are closed
  time.sleep(3) # TODO: One we have references to our children, we should just kill them
  for instance in instances:
    instances[instance]["manager"].stop()
    cache_path = CACHE_PREFIX / instance
    if cache_path.is_dir():
      rmtree(cache_path)

if __name__ == "__main__":
  atexit.register(shutdown_cleanup)
  main()
  atexit.unregister(shutdown_cleanup)
