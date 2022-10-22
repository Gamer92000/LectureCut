from ctypes import Structure, c_double, cdll, c_int, c_char_p, POINTER
import pathlib
import os

class CUT(Structure):
  _fields_ = [("start", c_double), ("end", c_double)]

def get_render():
  path = pathlib.Path(__file__).parent.resolve()
  lib = "render.dll" if os.name == "nt" else "librender.so"
  render = cdll.LoadLibrary(str(path / lib))

  render.init()

  render.prepare.argtypes = [c_char_p]
  render.prepare.restype = c_int
  render.render.argtypes = [c_int, c_int, POINTER(CUT), c_char_p]

  return render

