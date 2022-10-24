#!/usr/bin/env python3

import argparse
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
from helper import get_progress_callback
from module_manager import get_generator, get_render

from stats import print_stats

# RENDER DLL STUFF
render = get_render()
generator = get_generator()

N_CORES = multiprocessing.cpu_count()
PROCESSES = N_CORES // 4

instances = {}

dont_fucking_garbage_collect_these_things = []

def generate_cut_list(progress, ptypes, instance):
  """
  Generate a list of segments that should not be cut out of the video.
  The list is stored in the instances dictionary.

  instance -- the instance id
  """
  global instances, dont_fucking_garbage_collect_these_things
  file = instances[instance]["file"]
  callback = get_progress_callback(progress, ptypes)
  dont_fucking_garbage_collect_these_things.append(callback)
  cut_list = generator.generate(file.encode("utf-8"), callback)
  instances[instance]["cut_list"] = cut_list

def prepare_video(progress, ptypes, instance):
  """
  Prepare the video for cutting.
  This includes segmenting the video and analysing the segments.

  instance -- the instance id
  """
  global instances, dont_fucking_garbage_collect_these_things
  file_name = instances[instance]["file"]
  callback = get_progress_callback(progress, ptypes)
  dont_fucking_garbage_collect_these_things.append(callback)
  instances[instance]["render_id"] = render.prepare(file_name.encode("utf-8"), callback)

def transcode(progress, ptypes, instance):
  """
  Transcode the video.

  instance -- the instance id
  """
  global dont_fucking_garbage_collect_these_things
  process = instances[instance]["render_id"]
  cut_list = instances[instance]["cut_list"]
  output = instances[instance]["output"]
  callback = get_progress_callback(progress, ptypes)
  dont_fucking_garbage_collect_these_things.append(callback)
  render.render(
      process,
      output.encode("utf-8"),
      cut_list,
      quality,
      callback
  )

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

  ptypes = {}

  # rich.print("[green]1/3[/green] Preparing video")
  Parallel(n_jobs=2, require="sharedmem")([
      delayed(generate_cut_list)(progress, ptypes, instance),
      delayed(prepare_video)(progress, ptypes, instance)])
  # rich.print("[green]2/3[/green] Transcoding video")
  transcode(progress, ptypes, instance)
  # rich.print("[green]3/3[/green] Cleaning up")


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

if __name__ == "__main__":
  main()
