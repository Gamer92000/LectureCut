#!/usr/bin/env python3

import argparse
import atexit
import multiprocessing
import os
import textwrap
import time
import uuid

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
from module_manager import CUT, get_render

import vad
from helper import delete_directory_recursively
from stats import print_stats

# RENDER DLL STUFF
render = get_render()

N_CORES = multiprocessing.cpu_count()
PROCESSES = N_CORES // 4

# TODO: use pathlib
CACHE_PREFIX = "./" # needs to end with a slash 

instances = {}

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

def prepare_video(instance):
  """
  Prepare the video for cutting.
  This includes segmenting the video and analysing the segments.

  instance -- the instance id
  """
  global instances
  file_name = instances[instance]["file"]
  instances[instance]["render_id"] = render.prepare(file_name.encode("utf-8"))

def transcode(instance):
  """
  Transcode the video.

  instance -- the instance id
  """

  process = instances[instance]["render_id"]
  num_cuts = len(instances[instance]["cuts"])
  cuts = (CUT * num_cuts)()
  for i in range(num_cuts):
    cuts[i].start = instances[instance]["cuts"][i][0]
    cuts[i].end = instances[instance]["cuts"][i][1]
  output = instances[instance]["output"]
  render.render(process, num_cuts, cuts, output.encode("utf-8"))


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

def run(config):
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

  Parallel(n_jobs=2, require="sharedmem")([
      delayed(generate_cut_list)(instance),
      delayed(prepare_video)(instance)])
  transcode(instance)
  cleanup(instance)


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
      run({
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
    run({
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
