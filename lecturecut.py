#!/usr/bin/env python3

import ffmpeg
import os
import cv2
import time
import vad
from joblib import Parallel, delayed
import uuid
import enlighten
import time
from queue import Queue
from threading import Thread
import sys
import argparse
import textwrap

instances = {}

def reader(pipe, queue):
  try:
    with pipe:
      for line in iter(pipe.readline, b''):
        queue.put((pipe, line))
  finally:
    queue.put(None)

def deleteDirectoryRecursively(path):
  if os.path.exists(path):
    for filename in os.listdir(path):
      if os.path.isdir(path + filename):
        deleteDirectoryRecursively(path + filename + '/')
      else:
        os.remove(path + filename)
    os.rmdir(path)

def readProgress(pbar, ffmpeg_run):
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

def initCache(instance):
  cachePath = cachePrefix + f"/{instance}/"
  if os.path.exists(cachePath):
    raise Exception("Cache already exists")
  os.mkdir(cachePath)
  os.mkdir(cachePath + "/segments")
  os.mkdir(cachePath + "/cutSegments")

def cleanup(instance):
  cachePath = cachePrefix + f"/{instance}/"
  deleteDirectoryRecursively(cachePath)

def generateCutList(instance):
  global instances
  file = instances[instance]["file"]
  aggressiveness = instances[instance]["aggressiveness"]
  instances[instance]["cuts"] = vad.run(file, aggressiveness)

def prepareVideo(manager, instance):
  _splitVideo(manager, instance)
  _analyseSegments(manager, instance)

def _splitVideo(manager, instance):
  cachePath = cachePrefix + f"/{instance}/"
  file = instances[instance]["file"]

  totalInputLength = _getVideoLength(None, file)
  barTotal = int(totalInputLength * 1000)
  pbar = manager.counter(total=barTotal, desc='Segmenting ')

  split = (
    ffmpeg
    .input(file)
    .output(cachePath + 'segments/out%03d.ts', f='segment', c='copy', reset_timestamps=1)
    .global_args('-progress', 'pipe:1')
    .global_args('-loglevel', 'error')
    .global_args('-hide_banner')
    .overwrite_output()
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  readProgress(pbar, split)

def _analyseSegments(manager, instance):
  global instances
  instances[instance]["segments"] = {}
  cachePath = cachePrefix + f"/{instance}/"
  
  segments = os.listdir(cachePath + "segments")
  pbar = manager.counter(total=len(segments), desc='Analysing  ', unit='segments')

  durations = Parallel(n_jobs=2)(delayed(_getVideoLength)(pbar, f'{cachePath}segments/{path}') for path in segments)
  # calculate start end map
  total_duration = 0
  for i, duration in enumerate(durations):
    instances[instance]["segments"][i] = {
      "start": total_duration,
      "end": total_duration + duration,
    }
    total_duration += duration

def _getVideoLength(pbar, videoPath):
  video = cv2.VideoCapture(videoPath)
  fps = video.get(cv2.CAP_PROP_FPS)
  frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
  if pbar: pbar.update()
  return frame_count / fps

def transcode(manger, instance):
  global instances

  cachePath = cachePrefix + f"/{instance}/"
  segments = instances[instance]["segments"]
  cuts = instances[instance]["cuts"]
  quality = instances[instance]["quality"]

  pbar = manger.counter(total=len(segments), desc='Transcoding', unit='segments')

  # currentCut points to the first cut that ends after the current segment starts
  currentCut = 0

  for i in segments:
    # move all segments before the current cut or after the last cut to the cutSegments folder
    segment = segments[i]
    if currentCut >= len(cuts) or segment['end'] <= cuts[currentCut][0]:
      os.rename(f"{cachePath}segments/out{i:03d}.ts", f"{cachePath}cutSegments/out{i:03d}.ts")
      pbar.update()
      continue
    # if completely enclosed by a cut, skip
    if segment['start'] >= cuts[currentCut][0] and segment['end'] <= cuts[currentCut][1]:
      if segment['end'] == cuts[currentCut][1]:
        currentCut += 1
      pbar.update()
      continue
    # list of all things to be removed from the segment
    trimlist = []
    while currentCut < len(cuts) and (segment['end'] > cuts[currentCut][1]):
      start = max(segment['start'], cuts[currentCut][0])
      end = min(segment['end'], cuts[currentCut][1])
      trimlist.append((start, end))
      currentCut += 1
    if currentCut < len(cuts) and segment['end'] > cuts[currentCut][0]:
      start = max(segment['start'], cuts[currentCut][0])
      end = min(segment['end'], cuts[currentCut][1])
      trimlist.append((start, end))
    # invert the trimlist to get the list of things to keep
    keep = []
    if trimlist[0][0] > segment['start']:
      keep.append((segment['start'], trimlist[0][0]))
    for j in range(len(trimlist) - 1):
      keep.append((trimlist[j][1], trimlist[j + 1][0]))
    if trimlist[-1][1] < segment['end']:
      keep.append((trimlist[-1][1], segment['end']))

    # filter keep list to remove segments that are too short
    keep = [x for x in keep if x[1] - x[0] > 0.1]

    # convert keep list from global time to segment time
    keep = [(x[0] - segment['start'], x[1] - segment['start']) for x in keep]
    
    Parallel(n_jobs=2)(delayed(_transcodeSegment)(i, j, x, instance) for j,x in enumerate(keep))
    pbar.update()

def _transcodeSegment(i, j, trim, instance):
  cachePath = f'{cachePrefix}{instance}/'
  quality = instances[instance]["quality"]
  stream = ffmpeg.input(f'{cachePath}segments/out{i:03d}.ts')
  stream = stream.output(f'{cachePath}cutSegments/out{i:03d}_{j:02d}.ts', f='mpegts', ss=trim[0], to=trim[1], acodec="copy", vcodec="libx264", preset="fast", crf=quality, reset_timestamps=1, force_key_frames=0).global_args('-loglevel', 'quiet').global_args('-hide_banner')
  stream.run()

def concatSegments(manager, instance):
  cachePath = f'{cachePrefix}{instance}/'
  output = instances[instance]["output"]
  reencode = instances[instance]["reencode"]
  with open(f'{cachePath}list.txt', 'w') as f:
    for file in os.listdir(f'{cachePath}cutSegments'):
      f.write(f"file 'cutSegments/{file}'\n")
  lastSegment = len(instances[instance]["segments"])-1
  totalSegmentLength = instances[instance]["segments"][lastSegment]["end"]
  totalCutLength = sum([x[1] - x[0] for x in instances[instance]["cuts"]])
  totalOutputLength = totalSegmentLength - totalCutLength
  barTotal = int(totalOutputLength * 1000)
  pbar = manager.counter(total=barTotal, desc='Rendering  ')
  outputargs = {}
  if reencode:
    outputargs = {
      'vcodec': 'libx264',
      'preset': 'fast',
      'crf': instances[instance]["quality"],
      'acodec': 'aac',
    }
  else:
    outputargs = {
      'c': 'copy',
    }
  concat = (
    ffmpeg
    .input(f'{cachePath}list.txt', f='concat', safe=0)
    .output(output, **outputargs)
    .global_args('-progress', 'pipe:1')
    .global_args('-loglevel', 'error')
    .global_args('-hide_banner')
    .overwrite_output()
    .run_async(pipe_stdout=True, pipe_stderr=True)
  )
  readProgress(pbar, concat)

def run(manager, config):
  global instances

  instance = str(uuid.uuid4())
  instances[instance] = {
    "file": None,
    "output": None,
    "quality": 20,
    "aggressiveness": 3,
    "reencode": False,
  }
  for key in config:
    instances[instance][key] = config[key]

  fileString = manager.term.orange(os.path.basename(instances[instance]["file"]))
  mainFormat = f'Cutting {fileString}{{fill}}Stage: {{stage}}{{fill}}{{elapsed}}'
  status = manager.status_bar(status_format=mainFormat,
                              color='bold_bright_white_on_lightslategray',
                              justify=enlighten.Justify.CENTER, stage=f"[0/4] Initializing",
                              autorefresh=True, min_delta=0.2)

  initCache(instance)
  status.update(stage=f"[1/4] Preparing video")
  Parallel(n_jobs=2, require='sharedmem')([delayed(generateCutList)(instance), delayed(prepareVideo)(manager, instance)])
  status.update(stage=f"[2/4] Transcoding video")
  transcode(manager, instance)
  status.update(stage=f"[3/4] Rendering & Reencoding" if instances[instance]["reencode"] else "[3/4] Rendering video")
  concatSegments(manager, instance)
  cleanup(instance)
  status.update(stage=f"[4/4] Done 🎉", force=True)

cachePrefix = "./" # needs to end with a slash

def main():
  parser = argparse.ArgumentParser(description=textwrap.dedent('''
    LectureCut is a tool to remove silence from videos.

    It uses WebRTC's VAD to detect silence and ffmpeg to transcode the video.
    To speed up transcoding, a form of smart encoding is employed. This means that
    the video is split into segments and only the segments that need to be cut are
    transcoded. This results in a much faster transcoding process, but the output
    video will have a slightly lower quality than the input video.
  '''))

  parser.add_argument('-i', '--input', help='The video file to process', required=True)
  parser.add_argument('-o', '--output', help='The output file. If not specified, the input file will be overwritten', required=False)
  parser.add_argument('-q', '--quality', help='The quality of the output video. Lower is better. Default: 20', required=False, type=int, default=20)
  parser.add_argument('-a', '--aggressiveness', help='The aggressiveness of the VAD. Higher is more aggressive. Default: 3', required=False, type=int, default=3)
  parser.add_argument('-r', '--reencode', help='Reencode the video with a given video codec.', required=False, type=str)

  args = parser.parse_args()

  manager = enlighten.get_manager()
  name = manager.term.link('https://github.com/Gamer92000/LectureCut', 'LectureCut')
  author = manager.term.link('https://github.com/Gamer92000', 'Gamer92000')
  manager.status_bar(f' {name} - Made with ❤️ by {author}! ', position=1, fill='-', justify=enlighten.Justify.CENTER)

  # if input file is a directory, process all files in it
  if os.path.isdir(args.input):
    files = os.listdir(args.input)
    files = [f for f in files if os.path.isfile(os.path.join(args.input, f))]
    files = [os.path.join(args.input, f) for f in files]
    pbar = manager.counter(total=len(files), desc='Processing ')
    getFilePath = lambda x: x
    if args.output:
      if not os.path.isdir(args.output):
        os.mkdir(args.output)
      getFilePath = lambda x: os.path.join(args.output, os.path.basename(x))
    else:
      getFilePath = lambda x: os.path.splitext(os.path.basename(x))[0] + "_jumpcut" + os.path.splitext(os.path.basename(x))[1]
    for file in files:
      run(manager, {
        "file": file,
        "output": getFilePath(file),
        "quality": args.quality,
        "aggressiveness": args.aggressiveness,
        "reencode": args.reencode,
      })
      pbar.update()

  fallbackOutput = args.input.rsplit(".", 1)[0] + "_jumpcut." + args.input.rsplit(".", 1)[1]

  run(manager, {
    "file": args.input,
    "aggressiveness": args.aggressiveness,
    "quality": args.quality,
    "output": args.output if args.output else fallbackOutput,
    "reencode": args.reencode,
  })
  
  manager.stop()
  print()

if __name__ == "__main__":
  main()