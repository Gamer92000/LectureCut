from ctypes import Structure, c_double, c_long, cdll, c_int, c_char_p, POINTER
import pathlib
import os
import rich

from helper import FUNCTYPE

class CUT(Structure):
  _fields_ = [("start", c_double), ("end", c_double)]

class CUT_LIST(Structure):
  _fields_ = [("length", c_long), ("cuts", POINTER(CUT))]

path = pathlib.Path(__file__).parent.resolve()
path /= "modules"

def get_render():
  lib = "default.dll" if os.name == "nt" else "libdefault.so"
  render = cdll.LoadLibrary(str(path / "render" / lib))

  render.version.restype = c_char_p

  render.init.argtypes = [c_char_p]

  render.prepare.argtypes = [c_char_p, FUNCTYPE(None, c_char_p, c_double)]
  render.prepare.restype = c_int

  render.render.argtypes = [c_int, c_char_p, CUT_LIST, c_int, FUNCTYPE(None,  c_char_p, c_double)]

  render.init("quiet".encode("utf-8"))
  rich.print(f"Using render version [yellow]{render.version().decode('utf-8')}[/yellow]")

  return render

def get_generator():
  lib = "default.dll" if os.name == "nt" else "libdefault.so"
  generator = cdll.LoadLibrary(str(path / "generator" / lib))

  generator.version.restype = c_char_p

  generator.init.argtypes = [c_char_p]

  generator.generate.argtypes = [c_char_p, FUNCTYPE(None, c_char_p, c_double)]
  generator.generate.restype = CUT_LIST

  generator.init("quiet".encode("utf-8"))
  rich.print(f"Using generator version [yellow]{generator.version().decode('utf-8')}[/yellow]")

  return generator