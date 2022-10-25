#!/usr/bin/env python3

import argparse
import multiprocessing
import os
import textwrap
import time
import uuid
import filetype

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
from helper import get_progress_callback, print_dir_not_empty_warning, print_non_mp4_warning, print_reencode_missing_check_warning, raise_rich
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
  result = generator.generate(file.encode("utf-8"), aggressiveness, invert, callback)
  instances[instance]["cut_list"] = result.cuts
  instances[instance]["stats"] = result.stats

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

  ft = filetype.guess(config["file"])
  mime = ft.mime if ft else ""

  rich.print(f"  Input: [yellow]{config['file']}[/yellow]")
  rich.print(f" Output: [yellow]{config['output']}[/yellow]\n")
  if mime != "video/mp4":
    rich.print(f"[red]WARNING[/red]: Input file is not an mp4 file. This might cause problems.")

  instance = str(uuid.uuid4())
  instances[instance] = {
    "file": None,
    "output": None,
  }
  for key in config:
    instances[instance][key] = config[key]

  ptypes = {}

  prepare_video(progress, ptypes, instance)
  generate_cut_list(progress, ptypes, instance)
  transcode(progress, ptypes, instance)

  return instances[instance]["stats"]

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
          " Higher is more aggressive. Default: 1",
      required=False,
      type=int,
      default=1)
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
    aggressiveness = 3

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
  render_version = f"Render [yellow]{render.version().decode('utf-8')}[/yellow]"
  generator_version = f"Generator [yellow]{generator.version().decode('utf-8')}[/yellow]"
  version = f"{render_version} | {generator_version}"
  version = version.rjust(79)
  subtitle = f"{subtitle}{version}"
  subtitle = Align(subtitle, align="center")
  rich.print(subtitle)

def get_automatic_path(file_path):
  """
  Get the automatic name insert for the output file.
  """
  automatic_name_insert = "_lecturecut"

  if invert:
    automatic_name_insert = "_inverted" + automatic_name_insert

  name, ext = os.path.splitext(file_path)

  return name + automatic_name_insert + ext

def process_files_in_dir(args):
  get_file_path = lambda x: x
  if args.output:
    get_file_path = lambda x: os.path.join(args.output, os.path.basename(x))
  else:
    get_file_path = lambda x: get_automatic_path(x)

  files = sorted(os.listdir(args.input))
  files = [f for f in files if os.path.isfile(os.path.join(args.input, f))]
  files = [os.path.join(args.input, f) for f in files]
  files = [f for f in files if (ft := filetype.guess(f)) and ft.mime.startswith("video/")]
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

    for i, (input_file, output_file) in enumerate(files):
      prog = generate_progress_instance()
      group.renderables.insert(0, prog)
      stats = run(prog, {
        "file": input_file,
        "output": output_file
      })
      files[i] += stats
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
  greetings()
  args = parse_args()

  # ================
  # Input Validation
  # ================

  # input validation
  # because windows is seemingly designed by a 5 year old
  # we need to replace trailing double quotes with a backslash
  # ( see https://bugs.python.org/msg364246 )
  args.input = args.input.replace('"', '\\')
  if not os.path.exists(args.input):
    raise_rich("Input file or directory does not exist.")
  if not os.path.isfile(args.input) and not os.path.isdir(args.input):
    raise_rich("Input needs to be a file or a directory.")
  if os.path.isfile(args.input):
    ftype = filetype.guess(args.input)
    if not ftype:
      raise_rich("Input file has an unknown file type.")
    if not ftype.mime.startswith("video/"):
      raise_rich("Input file seems not to be a video.")

  # output validation
  if args.output:
    # output may not contain any illegal characters for paths
    if os.name == "nt":
      illegal_chars = "<>:\"|?*" + "".join([chr(x) for x in range(32)])
    else:
      illegal_chars = chr(0)
    if any([c in args.output for c in illegal_chars]):
      raise_rich("Output path contains illegal characters.")
    # if input is directory, output needs to be an empty directory, or not exist
    if os.path.isdir(args.input):
      if os.path.exists(args.output):
        if not os.path.isdir(args.output):
          raise_rich("Output path needs to be a directory.")
        if os.listdir(args.output):
          print_dir_not_empty_warning()
      else:
        try:
          os.mkdir(args.output)
        except:
          raise_rich("Could not create output directory.")
    # if input is file, output needs not to exist
    else:
      if os.path.exists(args.output):
        raise_rich("Output file already exists.")
  else:
    if not os.path.isdir(args.input):
      args.output = get_automatic_path(args.input)
      if os.path.exists(args.output):
        raise_rich("Output file already exists.")

  # quality validation
  if args.quality < 0 or args.quality > 51:
    raise_rich("Quality needs to be between 0 and 51.")

  # aggressiveness validation
  # FROM fvad:
  #  * A more aggressive (higher mode) VAD is more restrictive in reporting speech.
  #  * Put in other words the probability of being speech when the VAD returns 1 is
  #  * increased with increasing mode. As a consequence also the missed detection
  #  * rate goes up.
  if args.aggressiveness < 0 or args.aggressiveness > 3:
    raise_rich("Aggressiveness needs to be between 0 and 3.")

  # reencode validation
  if args.reencode:
    print_reencode_missing_check_warning()

  # ================
  # Input Processing
  # ================

  if os.path.isdir(args.input):
    process_files_in_dir(args)
  else:
    start = time.perf_counter()
    # with generate_progress_instance() as progress:
    progress = generate_progress_instance()
    stats = run(progress, {
      "file": args.input,
      "output": args.output
    })
    end = time.perf_counter()

    print_stats([(args.input, args.output, stats)], end - start)

if __name__ == "__main__":
  main()
