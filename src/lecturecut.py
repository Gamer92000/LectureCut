#!/usr/bin/env python3

import argparse
import atexit
import multiprocessing
import os
import sys
import textwrap
import time
import uuid
from itertools import takewhile

import ffmpeg
from joblib import Parallel, delayed

import rich
from rich.console import Group
from rich.live import Live
from rich.align import Align
from rich.progress import (
    MofNCompleteColumn,
    BarColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)

import vad
from helper import delete_directory_recursively, read_progress, get_video_length
from stats import print_stats

N_CORES = multiprocessing.cpu_count()
PROCESSES = N_CORES // 4

# TODO: use pathlib
CACHE_PREFIX = "./" # needs to end with a slash 

instances = {}

def init_cache(instance):
  """
  Create a cache directory for the given instance.
  The cache directory is used to store temporary files.

  instance -- the instance id
  """
  cache_path = CACHE_PREFIX + f"{instance}/"
  if os.path.exists(cache_path):
    raise Exception("Cache already exists")
  os.mkdir(cache_path)
  os.mkdir(cache_path + "/segments")
  os.mkdir(cache_path + "/cutSegments")

def cleanup(instance):
  """
  Delete the cache directory for the given instance.

  instance -- the instance id
  """
  cache_path = CACHE_PREFIX + f"/{instance}/"
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

def prepare_video(progress, instance):
  """
  Prepare the video for cutting.
  This includes segmenting the video and analysing the segments.

  progress -- the manager for the progress bars
  instance -- the instance id
  """
  _split_video(progress, instance)
  _analyse_segments(progress, instance)

def _split_video(progress, instance):
  """
  Split the video into segments based on keyframes.

  progress -- the manager for the progress bars
  instance -- the instance id
  """
  cache_path = CACHE_PREFIX + f"/{instance}/"
  file = instances[instance]["file"]

  total_input_length = get_video_length(file)
  bar_total = int(total_input_length * 1000)

  pbar = progress.add_task("[magenta]Segmenting", total=bar_total)

  split = (
    ffmpeg
    .input(file)
    .output(cache_path + "segments/out%05d.ts",
        f="segment",
        c="copy",
        reset_timestamps=1)
    .global_args("-progress", "pipe:1")
    .global_args("-loglevel", "error")
    .global_args("-hide_banner")
    .global_args("-nostdin")
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  read_progress(progress, pbar, split)

def _analyse_segments(progress, instance):
  """
  Analyse the length of each segment of the video.

  progress -- the manager for the progress bars
  instance -- the instance id
  """
  global instances
  instances[instance]["segments"] = {}
  cache_path = CACHE_PREFIX + f"/{instance}/"
  
  segments = sorted(os.listdir(cache_path + "segments"))

  pbar = progress.add_task("[magenta]Analysing", total=len(segments))

  durations = Parallel(n_jobs=PROCESSES)(
      delayed(get_video_length)
      (f"{cache_path}segments/{path}", progress, pbar)
      for path in segments)
  # calculate start end map
  total_duration = 0
  for i, duration in enumerate(durations):
    instances[instance]["segments"][i] = {
      "start": total_duration,
      "end": total_duration + duration,
    }
    total_duration += duration


def transcode(progress, instance):
  """
  Transcode the video.

  progress -- the manager for the progress bars
  instance -- the instance id
  """
  global instances

  cache_path = CACHE_PREFIX + f"/{instance}/"
  segments = instances[instance]["segments"]
  cuts = instances[instance]["cuts"]
  # check for argument Timestamps only "-tsonly"
  if ts_only:
    #write csv with timestamps
    with open("timestamps.csv", "w") as f:
      for cut in cuts:
        f.write(f"{cut[0]},{cut[1]},\n")
    exit("timestamps.csv written")
    
      
  

  pbar = progress.add_task("[magenta]Transcoding", total=len(segments))

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
      progress.update(pbar, advance=1)
      return

    # if completely enclosed by a cut, copy
    if first_cut[0] <= segment["start"] and first_cut[1] >= segment["end"]:
      os.rename(f"{cache_path}segments/out{i:05d}.ts",
          f"{cache_path}cutSegments/out{i:05d}.ts")
      progress.update(pbar, advance=1)
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
          .input(f"{cache_path}segments/out{i:05d}.ts")
          .output(f"{cache_path}cutSegments/out{i:05d}_{j:03d}.ts",
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
          .input(f"{cache_path}segments/out{i:05d}.ts")
          .output(f"{cache_path}cutSegments/out{i:05d}_{j:03d}.ts",
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
    progress.update(pbar, advance=1)
  Parallel(n_jobs=PROCESSES, require="sharedmem")(
      delayed(_process_segment)
      (i)
      for i in segments)


def concat_segments(progress, instance):
  """
  Concatenate the segments into a single video.

  progress -- the manager for the progress bars
  instance -- the instance id
  """
  cache_path = f"{CACHE_PREFIX}{instance}/"
  output = instances[instance]["output"]
  with open(f"{cache_path}list.txt", "w") as f:
    for file in sorted(os.listdir(f"{cache_path}cutSegments")):
      f.write(f"file 'cutSegments/{file}'\n")
  total_cut_length = sum([x[1] - x[0] for x in instances[instance]["cuts"]])
  bar_total = int(total_cut_length * 1000)
  
  pbar = progress.add_task("[magenta]Rendering", total=bar_total)
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
    .input(f"{cache_path}list.txt", f="concat", safe=0)
    .output(output, **outputargs)
    .global_args("-progress", "pipe:1")
    .global_args("-loglevel", "error")
    .global_args("-hide_banner")
    .global_args("-nostdin")
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  read_progress(progress, pbar, concat)

def generate_progress_instance():
  return Progress(
    TextColumn("{task.description}", justify="right"),
    BarColumn(bar_width=None),
    TextColumn("[progress.percentage]{task.percentage:>3.1f}%", justify="right"),
    "•",
    TimeRemainingColumn(),
    "•",
    TimeElapsedColumn(),
    transient=True,
  )

def run(progress, config):
  """
  Run the program on a single instance.

  progress -- the manager for the progress bars
  config -- the config for the instance
  """
  global instances

  rich.print(f"Input:  [yellow]{config['file']}[/yellow]")
  rich.print(f"Output: [yellow]{config['output']}[/yellow]\n")

  instance = str(uuid.uuid4())
  instances[instance] = {
    "file": None,
    "output": None,
  }
  for key in config:
    instances[instance][key] = config[key]

  init_cache(instance)
  Parallel(n_jobs=2, require="sharedmem")([
      delayed(generate_cut_list)(instance),
      delayed(prepare_video)(progress, instance)])
  transcode(progress, instance)
  # only continue if -tsonly is not set
  if not ts_only:
    concat_segments(progress, instance)
    cleanup(instance)


invert = False
quality = 20
aggressiveness = 3
reencode = False

def parse_args():
  """
  Parse the command line arguments.
  """
  global invert, quality, aggressiveness, reencode, ts_only
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
  parser.add_argument(
      "--tsonly",
      help="Invert the selection."+\
          " This will only output a csv with the cut timestamps.",
      required=False,
      action="store_true")

  args = parser.parse_args()

  if args.invert:
    invert = True
  if args.tsonly:
      ts_only = True
  if args.quality:
    quality = args.quality
  if args.aggressiveness:
    aggressiveness = args.aggressiveness
  if args.reencode:
    reencode = args.reencode

  if args.invert and not args.aggressiveness:
    aggressiveness = 1

  return args

def greetings():
  """
  Create a manager for the progress bars.
  """

  title = "██╗    ███████╗ ██████╗████████╗██╗   ██╗███████╗███████╗    ██████╗██╗  ██╗████████╗\n" + \
          "██║    ██╔════╝██╔════╝╚══██╔══╝██║   ██║██╔══██║██╔════╝   ██╔════╝██║  ██║╚══██╔══╝\n" + \
          "██║    █████╗  ██║        ██║   ██║   ██║██████╔╝█████╗     ██║     ██║  ██║   ██║\n" + \
          "██║    ██╔══╝  ██║        ██║   ██║   ██║██╔══██╗██╔══╝     ██║     ██║  ██║   ██║\n" + \
          "██████╗███████╗╚██████╗   ██║   ╚██████╔╝██║  ██║███████╗   ╚██████╗╚█████╔╝   ██║\n" + \
          "╚═════╝╚══════╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝    ╚═════╝ ╚════╝    ╚═╝"
  rich.print()
  title = Align(title, align="center")
  rich.print(title)
  subtitle = "[link=https://github.com/Gamer92000/LectureCut]Source Code[/link] - Made with ❤️ by [link=https://github.com/Gamer92000]Gamer92000[/link]"
  subtitle = Align(subtitle, align="center")
  rich.print(subtitle)

def get_automatic_name_insert():
  """
  Get the automatic name insert for the output file.
  """
  automatic_name_insert = "_lecturecut."

  if invert:
    automatic_name_insert = "_inverted" + automatic_name_insert

  return automatic_name_insert

def process_files_in_dir(args):
  get_file_path = lambda x: x
  if args.output:
    if not os.path.isdir(args.output):
      os.mkdir(args.output)
    get_file_path = lambda x: os.path.join(args.output, os.path.basename(x))
  else:
    get_file_path = lambda x: os.path.splitext(os.path.basename(x))[0] +\
        get_automatic_name_insert() +\
        x.rsplit(".", 1)[1]

  files = sorted(os.listdir(args.input))
  files = [f for f in files if os.path.isfile(os.path.join(args.input, f))]
  files = [os.path.join(args.input, f) for f in files]
  # TODO: Check if files are actually videos
  files = [(x, get_file_path(x)) for x in files]
  
  file_progress = Progress(
      "[progress.description]{task.description}",
      BarColumn(bar_width=None),
      MofNCompleteColumn(),
      "•",
      TimeElapsedColumn(),
      transient=True,
  )

  group = Group(file_progress)

  start = time.perf_counter()
  with Live(group):
    pbar = file_progress.add_task("[yellow]Videos", total=len(files))

    for input_file, output_file in files:
      prog = generate_progress_instance()
      group.renderables.insert(0, prog)
      run(prog, {
        "file": input_file,
        "output": output_file
      })
      file_progress.update(pbar, advance=1)
      group.renderables.remove(prog)
      rich.print(prog)
      rich.print()
  
    group.renderables.remove(file_progress)

  end = time.perf_counter()

  print_stats(files, end - start)

def main():
  """
  Main function.
  """
  args = parse_args()
  greetings()

  # because windows is seemingly designed by a 5 year old
  # we need to replace trailing double quotes with a backslash
  # ( see https://bugs.python.org/msg364246 )
  args.input = args.input.replace('"', '\\')

  if os.path.isdir(args.input):
    process_files_in_dir(args)
  else:
    if args.output == None:
      args.output = args.input.rsplit(".", 1)[0] +\
        get_automatic_name_insert() +\
        args.input.rsplit(".", 1)[1]

    start = time.perf_counter()
    with generate_progress_instance() as progress:
      run(progress, {
        "file": args.input,
        "output": args.output
      })
      end = time.perf_counter()

    print_stats([(args.input, args.output)], end - start)

def shotdown_cleanup():
  """
  Cleanup function that is called when the program is terminated.
  """
  if (len(instances) <= 0):
    return
  rich.print()
  rich.print("[red]Cleaning up after unexpected exit...")
  # sleep to make sure open file handles are closed
  time.sleep(3)
  for instance in instances:
    cachePath = f"{CACHE_PREFIX}{instance}/"
    if os.path.isdir(cachePath):
      delete_directory_recursively(cachePath)

if __name__ == "__main__":
  atexit.register(shotdown_cleanup)
  main()
  atexit.unregister(shotdown_cleanup)
