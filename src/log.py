# MIT License
# Simple logger with journald and file support

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
log_to_std_out = False

def log_init(mode=LogMode.AUTO, log_path=None, level=LogLevel.INFO, logToStdOut=False):
  """
  Sets up the logger. Must be called before the first call of log_print to set up the logger with non-default settings.
  
  log_init with default settings is called form log_print if the logger wasn't initialized.
  This function will do nothing if the logger is in an initialized state.

  Parameters
  ----------
  mode : LogMode
    AUTO, SYSTEMD : Try to write to journald or write to file if journald is unavailable.
    FILE : Write to file. The old logfile is overwritten. (Default path: `~/.local/var/log/LectureCut/log.txt` or `%LOCALAPPDATA%\LectureCut\log.txt`)
  log_path : Path
    Path of the log file in FILE mode. Ignored if journald is used.
  level : LogLevel
    Maximum level of log messages that are logged.
  logToStdOut : bool
    If true, write messages to stdout and into the log.
  """

  global log_is_initialized, log_mode, log_sock, log_file, log_level, log_to_std_out

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
        log_path = os.path.join(os.path.expanduser("~"), ".local", "var", "log", "LectureCut", "log.txt")
      else:
        log_path = os.path.join(os.getenv("%LOCALAPPDATA%"), "LectureCut", "log.txt") # TODO test with windows
    
    # TODO add exception handling
    if not os.path.exists(log_path):
      log_dir, _ = os.path.split(log_path)
      os.makedirs(log_dir, exist_ok=True)
    log_file = open(log_path, "w")
    log_mode = LogMode.FILE

  log_is_initialized = True
  log_level = level
  log_to_std_out = logToStdOut

def log_print(message, level=LogLevel.INFO, toStdOut=False):
  """
  Write message into the log and initializes the logger if necessary.
  
  Parameters
  ----------
  message : str
    Message that is written into the log.
  level : LogLevel
    Log-level of this log call.
  logToStdOut : bool
    If true, write messages to stdout and into the log.
  """

  if not log_is_initialized:
    log_init()

  if not log_level.to_val() <= level.to_val():
    return

  message = "{} {}".format(level.to_sting(), message)
  if toStdOut or log_to_std_out:
    print(message)
  if log_mode == LogMode.FILE:
    log_file.write("[{}] {}\n".format(time.time(), message))
  elif log_mode == LogMode.SYSTEMD:
    log_sock.send(bytes("LectureCut: {}".format(message), 'UTF-8'))

def log_close():
  """
  Closes file handles, sockets and sets the logger to an uninitialized state.
  """
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