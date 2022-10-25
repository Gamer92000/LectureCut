from ctypes import CDLL, CFUNCTYPE, Structure, c_double, c_long, c_int, c_char_p, POINTER, c_bool
import pathlib
import os

ffmpeg_log_lvl = "error"

class CUT(Structure):
  _fields_ = [("start", c_double), ("end", c_double)]

class CUT_LIST(Structure):
  _fields_ = [("length", c_long), ("cuts", POINTER(CUT))]

class GENERATOR_STATS(Structure):
  _fields_ = [("len_pre_cut", c_double), ("len_post_cut", c_double)]

class GENERATOR_RESULT(Structure):
  _fields_ = [("cuts", CUT_LIST), ("stats", GENERATOR_STATS)]

path = pathlib.Path(__file__).parent.resolve()
path /= "modules"

def get_render():
  lib = "default.dll" if os.name == "nt" else "libdefault.so"
  render = CDLL(str(path / "render" / lib))

  render.version.restype = c_char_p

  render.init.argtypes = [c_char_p]

  render.prepare.argtypes = [c_char_p, CFUNCTYPE(None, c_char_p, c_double)]
  render.prepare.restype = c_char_p

  render.render.argtypes = [c_char_p, c_char_p, CUT_LIST, c_int, CFUNCTYPE(None, c_char_p, c_double)]

  render.init(ffmpeg_log_lvl.encode("utf-8"))
  return render

def get_generator():
  lib = "default.dll" if os.name == "nt" else "libdefault.so"
  generator = CDLL(str(path / "generator" / lib))

  generator.version.restype = c_char_p

  generator.init.argtypes = [c_char_p]

  generator.generate.argtypes = [
    c_char_p,
    c_int,
    c_bool,
    CFUNCTYPE(None, c_char_p, c_double)
  ]
  generator.generate.restype = GENERATOR_RESULT

  generator.init(ffmpeg_log_lvl.encode("utf-8"))
  return generator