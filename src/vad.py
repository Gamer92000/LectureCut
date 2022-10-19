import math

import cv2
import ffmpeg
import webrtcvad

KERN_SIZE = 30

def read_audio(path):
  """
  Reads the video file.
  
  returns (PCM audio data, sample rate).
  """
  out, _ = (
    ffmpeg
    .input(path)
    .output("pipe:", format="s16le", acodec="pcm_s16le", ac=1, ar="16k")
    .global_args("-loglevel", "quiet")
    .global_args("-hide_banner")
    .global_args("-nostdin")
    .run(capture_stdout=True)
  )
  return out, 16000


class Frame(object):
  """Represents a "frame" of audio data."""
  def __init__(self, bytes, timestamp, duration):
    self.bytes = bytes
    self.timestamp = timestamp
    self.duration = duration


def frame_generator(frame_duration_ms, audio, sample_rate):
  """
  Generates audio frames from PCM audio data.
  Takes the desired frame duration in milliseconds, the PCM data, and
  the sample rate.
  Yields Frames of the requested duration.

  frame_duration_ms -- The frame duration in milliseconds.
  audio -- The PCM data.
  sample_rate -- The sample rate of the data.
  """
  n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
  offset = 0
  timestamp = 0.0
  duration = (float(n) / sample_rate) / 2.0
  while offset + n < len(audio):
    yield Frame(audio[offset:offset + n], timestamp, duration)
    timestamp += duration
    offset += n


def build_gauss_kernel(n_frames):
  """
  n_frames: number of frames to consider (needs to be odd)
  """
  def gauss(x):
    """
    calculates a sample of the continuous gaussian function
    # sigma is fixed at 1
    # normalization is skipped for simplicity
    """
    return 1 * math.exp(- (float(x)**2) / 2)

  if n_frames <= 1:
    scale = 1
  else:
    scale = 1 / (n_frames // 2) * 2
  kernel = [0.0] * n_frames
  for i in range(n_frames):
    kernel[i] = gauss((i - n_frames // 2) * scale)
  kernelSum = sum(kernel)
  kernel = [x / kernelSum for x in kernel]
  return kernel

def clip_gauss_kernel(kernel, side, cutoff):
  """
  removes part of the kernel and normalizes the remaining part
  kernel: gaussian kernel
  side: "left" or "right"
  cutoff: number of elments to cut off
  """
  if side == "left":
    kernel = kernel[cutoff:]
  elif side == "right":
    kernel = kernel[:-cutoff]
  kernelSum = sum(kernel)
  kernel = [x / kernelSum for x in kernel]
  return kernel

def vad_collector(sample_rate, frame_duration_ms, kernel_size, vad, frames):
  """
  Filters out non-voiced audio frames.
  Given a webrtcvad.Vad and a source of audio frames, returns a list
  of (start, end) timestamps for the voiced audio.
  Uses a Gaussian filter to smooth the probability of being voiced
  over time.
  
  Arguments:
  sample_rate -- The audio sample rate, in Hz.
  frame_duration_ms -- The frame duration in milliseconds.
  kernel_size -- The number of frames to include in the smoothing per side.
  vad -- An instance of webrtcvad.Vad.
  frames -- a source of audio frames (sequence or generator).
  
  returns -- a list of (start, end) timestamps.
  """
  vad_frames = [(frame, vad.is_speech(frame.bytes, sample_rate))
                for frame in frames]

  kernel = build_gauss_kernel(kernel_size * 2 + 1)
  filtered_vad_frames = []
  for i in range(len(vad_frames)):
    if i < kernel_size:
      tmpKernel = clip_gauss_kernel(kernel, "left", kernel_size - i)
      filtered_vad_frames.append((vad_frames[i][0], sum([x[1] * y
          for x, y in
          zip(vad_frames[i : i+kernel_size+1], tmpKernel)
          ])))
    elif i > len(vad_frames) - kernel_size :
      tmpKernel = clip_gauss_kernel(kernel, "right", 
          kernel_size - (len(vad_frames) - i))
      filtered_vad_frames.append((vad_frames[i][0], sum([x[1] * y
          for x, y in
          zip(vad_frames[i-kernel_size : i+1], tmpKernel)
          ])))
    else:
      filtered_vad_frames.append((vad_frames[i][0], sum([x[1] * y
          for x, y in
          zip(vad_frames[i-kernel_size : i+kernel_size+1], kernel)
          ])))

  segments = [(x[0].timestamp, x[0].timestamp+x[0].duration)
      for x in
      filtered_vad_frames if x[1] > 0.5]
  # merge segments when no more than .2 second between them
  newSegments = []
  i = 0
  while i < len(segments)-1:
    startSegment = i
    while i < (len(segments)-1) and segments[i][1] + .2 >= segments[i+1][0]:
      i += 1
    newSegments.append((segments[startSegment][0], segments[i][1]))
    i += 1

  # rount to 4 decimal places
  newSegments = [(round(x[0], 4), round(x[1], 4)) for x in newSegments]

  return newSegments

def run(file, aggressiveness, invert=False):
  """
  Given a file path, aggressiveness, and invert flag, returns a list of
  (start, end) timestamps for the voiced audio.

  file: path to the audio file
  aggressiveness: aggressiveness of the VAD
  invert: if True, returns a list of (start, end) timestamps
          for the non-voiced audio
  """
  audio, sample_rate = read_audio(file)
  vad = webrtcvad.Vad(aggressiveness)
  frames = frame_generator(30, audio, sample_rate)
  frames = list(frames)
  segments = vad_collector(sample_rate, 30, KERN_SIZE, vad, frames)  
  cuts = segments

  if invert:
    video = cv2.VideoCapture(file)
    fps = video.get(cv2.CAP_PROP_FPS)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps
    cuts = []
    if segments[0][0] > 0:
      cuts.append((0, segments[0][0]))
    for j in range(len(segments) - 1):
      cuts.append((segments[j][1], segments[j + 1][0]))
    if segments[-1][1] < duration:
      cuts.append((segments[-1][1], duration))
  
  return cuts