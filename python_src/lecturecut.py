#!/usr/bin/env python3

import multiprocessing
import os
import time
import uuid
import filetype
from arguments import parse_args, validate_args

import rich
from rich.console import Group
from rich.live import Live
from rich.progress import (
    MofNCompleteColumn,
    BarColumn,
    Progress,
    TimeElapsedColumn,
)

from helper import (
  generate_progress_instance,
  get_automatic_path,
  get_progress_callback
)
from printer import greetings
from module_manager import get_generator, get_render
from stats import print_stats

# =================
# DYNAMIC LIBRARIES
# =================

render = get_render()
generator = get_generator()


# ================
# GLOBAL VARIABLES
# ================

# multiprocessing variables
N_CORES = multiprocessing.cpu_count()
PROCESSES = N_CORES // 4

# per instance storage
instances = {}

# global options
invert = False
quality = 20
aggressiveness = 1
reencode = False

# stuff in here can be seen as a potential memory leak
# but that doesn't matter because the program will exit anyway
garbage_collection_preventer = []


# ==========
# FUNCTIONAL
# ==========

def generate_cut_list(progress, ptypes, instance):
  """
  Generate a list of segments that should not be cut out of the video.
  The list is stored in the instances dictionary.

  instance -- the instance id
  """
  global instances, garbage_collection_preventer
  file = instances[instance]["file"]
  callback = get_progress_callback(progress, ptypes)
  garbage_collection_preventer.append(callback)
  result = generator.generate(
    file.encode("utf-8"), 
    aggressiveness,
    invert,
    callback
  )
  instances[instance]["cut_list"] = result.cuts
  instances[instance]["stats"] = result.stats


def prepare_video(progress, ptypes, instance):
  """
  Prepare the video for cutting.
  This includes segmenting the video and analysing the segments.

  instance -- the instance id
  """
  global instances, garbage_collection_preventer
  file_name = instances[instance]["file"]
  callback = get_progress_callback(progress, ptypes)
  garbage_collection_preventer.append(callback)
  instances[instance]["render_id"] = render.prepare(
    file_name.encode("utf-8"),
    callback
  )


def transcode(progress, ptypes, instance):
  """
  Transcode the video.

  instance -- the instance id
  """
  global garbage_collection_preventer
  process = instances[instance]["render_id"]
  cut_list = instances[instance]["cut_list"]
  output = instances[instance]["output"]
  callback = get_progress_callback(progress, ptypes)
  garbage_collection_preventer.append(callback)
  render.render(
      process,
      output.encode("utf-8"),
      cut_list,
      quality,
      callback
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
    rich.print(f"[red]WARNING[/red]: Input file is not an mp4 file."+\
        " This might cause problems.")

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


def process_files_in_dir(args):
  """
  Main logic for processing multiple files.

  args -- The parsed command line arguments.
  """
  get_file_path = lambda x: x
  if args.output:
    get_file_path = lambda x: os.path.join(args.output, os.path.basename(x))
  else:
    get_file_path = lambda x: get_automatic_path(x, invert)

  files = sorted(os.listdir(args.input))
  files = [f for f in files if os.path.isfile(os.path.join(args.input, f))]
  files = [os.path.join(args.input, f) for f in files]
  files = [f for f in files if os.path.isfile(f)]
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


def process_single_file(args):
  """
  Main logic for processing a single file.

  args -- The parsed command line arguments.
  """
  start = time.perf_counter()
  with generate_progress_instance() as progress:
    stats = run(progress, {
      "file": args.input,
      "output": args.output
    })
  end = time.perf_counter()

  print_stats([(args.input, args.output, stats)], end - start)


def set_global_options(args):
  """
  Set the global options.

  args -- The parsed command line arguments.
  """
  global invert, quality, aggressiveness, reencode
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


def main():
  """
  Main function.
  """
  # draw banner
  render_version = render.version().decode('utf-8')
  generator_version = generator.version().decode('utf-8')
  greetings(render_version, generator_version)
  
  # parse arguments
  args = parse_args()
  set_global_options(args)

  # validate arguments
  validate_args(args)

  # process files
  if os.path.isdir(args.input):
    process_files_in_dir(args)
  else:
    process_single_file(args)


# ===========
# ENTRY POINT
# ===========
if __name__ == "__main__":
  main()
