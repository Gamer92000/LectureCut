import argparse
import os
import textwrap
import filetype
from helper import get_automatic_path

from printer import (
  print_dir_not_empty_warning,
  print_reencode_missing_check_warning,
  raise_rich
)

def parse_args():
  """
  Parse the command line arguments.
  """
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
          " LectureCut will automatically generate a name.",
      required=False)
  parser.add_argument(
      "-q", "--quality",
      help="The quality of the parts of the video"+\
          " that need to be transcoded."+\
          " Lower is better. Default: 20",
      required=False,
      type=int,
      default=20)
  parser.add_argument(
      "-a", "--aggressiveness",
      help="The aggressiveness of VAD."+\
          " Higher is more aggressive. Default: 1 (3 if invert)",
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

  # because windows is seemingly designed by a 5 year old
  # we need to replace trailing double quotes with a backslash
  # ( see https://bugs.python.org/msg364246 )
  args.input = args.input.replace('"', '\\')

  return args


def validate_args(args):
  """
  Custom validator for the command line arguments.

  This is needed over the built-in argparse validators because
  some checks depend on the values of other arguments.

  args -- The parsed command line arguments.
  """
  # input validation
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
      args.output = get_automatic_path(args.input, args.invert)
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