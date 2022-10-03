import socket
import os
from enum import Enum
import time


class LogMode(Enum):
  SYSTEMD = 0
  FILE = 1
  AUTO = 0


class LogLevel(Enum):
  DEBUG = 0
  INFO = 1
  IMPORTANT = 2

  def to_sting(self):
    if self == self.DEBUG:
      return "debug:"
    elif self == self.INFO:
      return "info:"
    else:
      return "important:"
  
  def to_val(self):
    if self == self.DEBUG:
      return 0
    elif self == self.INFO:
      return 1
    else:
      return 2

log_is_initialized = False
log_mode = None
log_sock = None
log_file = None
log_level = None


def log_init(mode=LogMode.AUTO, log_path=None, level=LogLevel.INFO):
  global log_is_initialized, log_mode, log_sock, log_file, log_level

  # check if log system already initialized
  if log_is_initialized:
    return

  # setup journald logging
  if os.name == "posix" and mode == LogMode.SYSTEMD:
    try:
      log_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
      log_sock.connect("/dev/log")
      log_mode = LogMode.SYSTEMD
    except FileNotFoundError:
      mode = LogMode.FILE

  # setup file logging
  if mode == LogMode.FILE:

    # set default path
    if log_path == None:
      if os.name == "posix":
        log_path = os.path.join(os.path.expanduser("~"), ".local", "LectureCut", "log.txt")
      else:
        log_path = os.path.join(os.getenv("%LOCALAPPDATA%"), "LectureCut", "log.txt")
    
    # TODO add exception handling
    if not os.path.exists(log_path):
      log_dir, _ = os.path.split(log_path)
      os.mkdirs(log_dir, exist_ok=True)
    log_file = open(log_path, "a")
    log_mode = LogMode.FILE

  log_is_initialized = True
  log_level = level

def log_print(message, level=LogLevel.INFO, toStdOut=False):
  if not log_is_initialized:
    log_init()
  if not log_level.to_val() <= level.to_val():
    return
  message = "{} {}".format(level.to_sting(), message)
  if toStdOut:
    print(message)
  if log_mode == LogMode.FILE:
    log_file.write("[{}] {}\n".format(time.time(), message))
  elif log_mode == LogMode.SYSTEMD:
    log_sock.send(bytes("LectureCut: {}".format(message), 'UTF-8'))

def log_close():
  global log_is_initialized

  # check if log is initialized
  if not log_is_initialized:
    return

  # close sockets or file handles
  if log_mode == LogMode.SYSTEMD:
    log_sock.close()
  else:
    log_file.close()

  log_is_initialized == False