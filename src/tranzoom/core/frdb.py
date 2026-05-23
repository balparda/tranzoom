# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal Database core logic."""

from __future__ import annotations

import json
import logging
import threading
from collections import abc
from pathlib import Path
from typing import Self, TypedDict, cast

from transcrypto.core import aes, key
from transcrypto.utils import base as tbase
from transcrypto.utils import config as app_config
from transcrypto.utils import timer

from tranzoom import __version__
from tranzoom.core import fractal

# DB constants

_DB_FILE_NAME = 'tranZ_DB.json'  # default DB file name
_DB_COMPRESS_LEVEL = 5  # default compression level for DB saving
_DB_DISK_LOCK: threading.Lock = threading.Lock()  # lock for thread-safe DB operations

_PicklePrettyJSON: abc.Callable[[tbase.JSONDict], bytes] = lambda d: json.dumps(
  d, indent=2, separators=(',', ': ')
).encode('utf-8')


class Error(fractal.Error):
  """Base fractal database exception."""


class FrameData(TypedDict):
  """Frame data type, for storing frame metadata and parameters.

  Attributes:
    frm (tbase.JSONDict): (CORE DATA) frame.Frame.json
    mag (float): (CACHE) frame magnitude; 10^(mag) is the magnification proper but that can
        be beyond float so we make sure to keep just the magnitude
    cps (dict[str, ComputationData]): (CHILDREN) one frame can have multiple computations; dict of
        {cp_hash: ComputationData}

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # CORE DATA
  frm: tbase.JSONDict  # frame.Frame.json

  # CACHE
  mag: float  # frame magnitude

  # CHILDREN: one frame can have multiple computations
  cps: dict[str, ComputationData]  # {cp_hash: ComputationData}


class ComputationData(TypedDict):
  """Computation data type, for storing computation metadata and parameters.

  Attributes:
    frm (str): (CORE DATA) Frame hash (frame_hash) -> points back to father Frame
    cp (str): (CORE DATA) ComputationParameters hash (cp_hash) - we don't store here,
        look in _DBType.cps
    tm (int): (CACHE) timestamp of computation (raw data) creation
    raw_data_path (str): (CACHE) path to raw data file (if not on disk, this computation
        entry becomes moot!) so we must have it here or remove the entry
    renders (dict[str, ImageData]): (CHILDREN) one computation can have multiple renders;
        dict of {render_hash: ImageData}

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # CORE DATA: Frame + ComputationParameters = a specific computation
  frm: str  # Frame hash (frame_hash)
  cp: str  # ComputationParameters hash (cp_hash) - look in _DBType.cps

  # CACHE: the raw data is the most expensive to compute, so we store it
  tm: int  # timestamp of computation
  raw_data_path: str  # path to raw data file

  # CHILDREN: one computation can have multiple renders
  renders: dict[str, ImageData]  # {render_hash: ImageData}


class ImageCoreKey(TypedDict):
  """The 3 hashes that uniquely identify an image: frame_hash, cp_hash, and render_hash.

  Attributes:
    frm (str): (CORE DATA) Frame hash (frame_hash) -> points back to grandfather Frame
    cp (str): (CORE DATA) ComputationParameters hash (cp_hash) -> points back to
        father ComputationParameters
    render (str): (CORE DATA) RenderParameters hash (render_hash) - we don't store here,
        look in _DBType.renders

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # Frame + ComputationParameters + RenderParameters = a specific PNG image
  frm: str  # Frame hash
  cp: str  # ComputationParameters hash
  render: str  # RenderParameters hash (render_hash) - look in _DBType.renders


class ImageData(TypedDict):
  """Image data type, for storing PNG image/frame metadata and parameters. CANNOT be a video/GIF.

  Attributes:
    core (ImageCoreKey): (CORE DATA) the 3 hashes that uniquely identify an image: frame_hash,
        cp_hash, and render_hash
    data_hash (str): (CACHE) hash of the image PNG data; if we have this entry,
        we must have the hash!
    tm (int | None): (CACHE) timestamp of rendered image creation; None if not saved
    rendered_path (str | None): (CACHE) path to image PNG file; None if not saved

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # CORE DATA: Frame + ComputationParameters + RenderParameters = a specific PNG image
  core: ImageCoreKey  # we nest the core data

  # CACHE
  data_hash: str  # hash of the image PNG data
  tm: int | None  # timestamp of rendered image creation; None if not saved
  rendered_path: str | None  # path to image PNG file; None if not saved


class ZoomData(TypedDict):
  """Video/GIF zoom data type, for storing zoom metadata and parameters.

  Attributes:
    zoom (tbase.JSONDict): (CORE DATA) image.ZoomParameters.json
    fps (float): (CACHE) frames-per-second; number of total frames is exactly len(frames)
    step_mag (float): (CACHE) video step scalar magnification (magnification per frame step)
    data_hash (str): (CACHE) hash of the video/GIF data; if we have this entry,
        we must have the hash!
    tm (int | None): (CACHE) timestamp of rendered video/GIF creation; None if not saved
    rendered_path (str | None): (CACHE) path to video/GIF file; None if not saved
    frames (list[str]): ("CHILDREN") list of Frame hashes -> grandfather Frames; ordered by
        magnification ascending; len >=3
    markers (list[str]): ("CHILDREN") subset of frames entry: key Frame(s) for color
        normalization; len >=1

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # CORE DATA: ZoomParameters = a specific video, the rest is computed
  zoom: tbase.JSONDict  # image.ZoomParameters.json

  # CACHE
  fps: float  # = len(`frames`) / `zoom.duration`
  step_mag: float  # video step SCALAR magnification (total magnitude is in `zoom.mag`)
  data_hash: str  # hash of the video/GIF data = SHA-256('|'.join(data_hash for all frames))
  tm: int | None  # timestamp of rendered video/GIF creation; None if not saved
  rendered_path: str | None  # path to video/GIF file; None if not saved

  # "CHILDREN" would be the individual frames/images that compose the video;
  # we compute this from core data, so this could be "CACHE" too...
  frames: list[str]  # Frame hashes; ordered by magnification ascending; len >=3
  markers: list[str]  # subset of frames entry: key Frame(s); len >=1


class _DBType(TypedDict):
  """DB object type.

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.
  """

  # DB internal data and metadata
  db_version: int  # DB version; increment on save
  app_version: str  # package version (tranzoom.__version__) at time of last save
  last_save: int  # timestamp of last save

  # actual fractals data
  frames: dict[str, FrameData]  # {frame_hash: FrameData}
  cps: dict[str, tbase.JSONDict]  # {cp_hash: frame.ComputationParameters.json}
  renders: dict[str, tbase.JSONDict]  # {render_hash: image.RenderParameters.json}
  videos: dict[str, ZoomData]  # {video_hash: ZoomData}, video_hash is the ZoomData.sha hash!

  # suggested indexes:
  images_idx: dict[str, ImageCoreKey]  # {data_hash: ImageCoreKey}
  videos_idx: dict[str, str]  # {data_hash: video_hash}
  img_paths_idx: dict[str, str]  # {img_path: data_hash} for easy lookup of PNG image paths
  video_paths_idx: dict[str, str]  # {video_path: video_hash} for easy lookup of GIF/video paths


def _DBTypeFactory(overrides: dict[str, object] | None = None) -> _DBType:
  """Create new _DBType object with default values.

  Args:
    overrides (dict[str, object] | None): dict of fields to override from the defaults; if None,
        will use all defaults

  Returns:
    _DBType: A new _DBType object with default values.

  """
  obj: _DBType = {
    'db_version': 0,
    'app_version': __version__,  # set to current package version on creation
    'last_save': timer.Now(),
    'frames': {},
    'cps': {},
    'renders': {},
    'videos': {},
    'images_idx': {},
    'videos_idx': {},
    'img_paths_idx': {},
    'video_paths_idx': {},
  }
  obj.update(overrides or {})  # type: ignore[typeddict-item]
  return obj


class FractalDatabase:
  """Fractal database class, for storing and retrieving frames/images and their metadata."""

  # process-wide lock: only one FractalDatabase instance may be open at any time, in any thread:
  # acquired in __init__() and released in Close() or __exit__().
  _CONTEXT_LOCK: threading.Lock = threading.Lock()

  def __init__(
    self,
    appconfig: app_config.AppConfig,
    *,
    read_only: bool = False,
    aes_key: aes.AESKey | None = None,
    safe_save: bool = True,
    compress_save: bool = False,
    format_json: bool = True,
  ) -> None:
    """Initialize the fractal database.

    Args:
      appconfig (app_config.AppConfig): AppConfig object for configuration and directory management.
      read_only (bool): If True, the database will be opened in read-only mode; default is
          False, meaning it can be read and written to; if True, any attempt to write to the DB
          will raise an error.
      aes_key (aes.AESKey | None): (default None) Optional AES key for encrypting/decrypting the
          database file
      safe_save (bool): (default True) Whether to use a safe save method that reads the existing
          DB file before writing, to prevent data loss from clobbering; if False, it will
          overwrite the file directly
      compress_save (bool): (default False) Whether to compress the DB file when saving; if True,
          it will save as a compressed file
      format_json (bool): (default True) Whether to format the JSON output with indentation
          for readability.

    Raises:
      Error: if another instance of FractalDatabase is already open

    """
    self._config: app_config.AppConfig = appconfig
    self._path: Path = self._config.dir / _DB_FILE_NAME
    self._read_only: bool = read_only
    self._key: aes.AESKey | None = aes_key
    self._safe_save: bool = safe_save
    self._compress_save: bool = compress_save
    self._format_json: bool = format_json
    self._db: _DBType
    self._closed: bool = False  # True once Close() / __exit__ has been called
    self._open = timer.Timer('FractalDatabase', emit_log=False)
    if not FractalDatabase._CONTEXT_LOCK.acquire(blocking=False):
      raise Error('Cannot open FractalDatabase: another instance is already open!')
    try:
      self._InitLoad()
    except Exception:
      FractalDatabase._CONTEXT_LOCK.release()  # don't leak the lock if init fails
      self._closed = True
      raise

  def _InitLoad(self) -> None:
    """Load the database from disk (or create a new one). Called only from __init__()."""
    with _DB_DISK_LOCK:  # ensure thread-safe load operations
      if self._path.exists():
        self._db = cast(
          '_DBType',
          self._config.DeSerialize(
            config_name=_DB_FILE_NAME, decryption_key=self._key, unpickler=key.UnpickleJSON
          ),
        )
        logging.info(f'Loaded DB from "{self._path}": {self.label}')
      else:
        self._db = _DBTypeFactory()
        logging.warning(f'DB file not found, will work in "{self._config.dir}", {self.label}')
    if self._read_only:
      logging.warning('ATTENTION: Database opened in read-only mode, changes will not be saved!')

  def __enter__(self) -> Self:
    """Context manager entry, returns self.

    Returns:
      Self: self, for use within the context

    """
    return self

  def __exit__(
    self,
    exc_type: type[BaseException] | None,
    _exc_value: BaseException | None,
    _traceback: object,
  ) -> None:
    """Context manager exit. Calls Close() unless an exception occurred.

    Args:
      exc_type (type[BaseException] | None): exception type, if any
      _exc_value (BaseException | None): exception value, if any
      _traceback (object): traceback object, if any

    """
    if exc_type is not None:
      logging.error('Exception occurred in Database context: *NOT* saving DB due to exception')
      self._DoClose(save=False)
      return
    self._DoClose(save=True)

  def Close(self) -> None:
    """Save and close the database, releasing the process-wide lock.

    Must be called exactly once when done with the database (unless using as a context manager).
    Subsequent calls are silently ignored.

    """
    self._DoClose(save=True)

  def _DoClose(self, *, save: bool) -> None:
    """Close implementation: optionally saves, logs, and releases the lock.

    Args:
      save (bool): whether to save the database before releasing the lock

    """
    if self._closed:
      logging.warning('FractalDatabase already closed, ignoring redundant close call')
      return
    self._closed = True
    logging.info(f'Database was open for {self._open}')
    try:
      if save:
        self.Save()
    finally:
      FractalDatabase._CONTEXT_LOCK.release()

  @property
  def label(self) -> str:
    """Get a human-readable label for the database, for logging and display purposes.

    Returns:
      string '#<N>@<tm>'

    """
    return _DBLabel(self._db)

  def Save(self) -> None:
    """Save the database to file.

    Raises:
      Error: if safe_save is enabled and the existing DB on disk differs from the loaded DB

    """
    if self._read_only:
      logging.warning('Database in read-only mode: will *NOT* save! (would have saved now)')
      return
    with _DB_DISK_LOCK:  # ensure thread-safe save operations
      # check on previous save
      if self._safe_save and self._path.exists():
        logging.debug('Safe save enabled, reading existing DB before saving to prevent data loss')
        existing_db: _DBType = cast(
          '_DBType',
          self._config.DeSerialize(
            config_name=_DB_FILE_NAME,
            decryption_key=self._key,
            unpickler=key.UnpickleJSON,
            silent=True,
          ),
        )
        if (
          existing_db['db_version'] != self._db['db_version']
          or existing_db['last_save'] != self._db['last_save']
        ):
          raise Error(
            f'DB on disk {_DBLabel(existing_db)} differs from loaded DB {self.label}, '
            'aborting save to prevent data loss'
          )
      # update DB metadata before saving
      prev_label: str = self.label
      self._db.update(
        # this part is always updated on save
        {
          'db_version': self._db['db_version'] + 1,  # increment DB version on each save
          'app_version': __version__,  # set to current package version on creation
          'last_save': timer.Now(),
        }
      )
      # save the DB to disk with optional encryption and compression
      self._config.Serialize(
        cast('tbase.JSONDict', self._db),
        config_name=_DB_FILE_NAME,
        encryption_key=self._key,
        pickler=_PicklePrettyJSON if self._format_json else key.PickleJSON,
        compress=_DB_COMPRESS_LEVEL if self._compress_save else None,
      )
      logging.info(f'DB saved to "{self._path}": {prev_label} -> {self.label}')


def _DBLabel(db: _DBType) -> str:
  """Get a human-readable label for the database, for logging and display purposes.

  Args:
    db (_DBType): The database object to get the label for.

  Returns:
    str: string '#<N>@<tm>'

  """
  return f'#{db["db_version"]}@{timer.TimeStr(db["last_save"])}'
