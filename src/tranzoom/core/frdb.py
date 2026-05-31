# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal Database core logic."""

from __future__ import annotations

import dataclasses
import json
import logging
import pathlib
import threading
from collections import abc
from typing import Self, TypedDict, cast

from transcrypto.core import aes, key
from transcrypto.utils import base as tbase
from transcrypto.utils import config as app_config
from transcrypto.utils import human, timer

from tranzoom import __version__
from tranzoom.core import fractal, frame, image

# TODO: commands to look at data in the DB
# DB constants

_DB_FILE_NAME = 'tranZ_DB.json'  # default DB file name
_DB_COMPRESS_LEVEL = 5  # default compression level for DB saving: fast
_IMG_DATA_COMPRESS_LEVEL = 20  # default compression level for image data saving: VERY high
_DB_DISK_LOCK: threading.Lock = threading.Lock()  # lock for thread-safe DB operations

ExistingPathsFilter: abc.Callable[[list[str]], list[str]] = lambda lp: [
  p for p in lp if pathlib.Path(p).exists()
]

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
    tm (int): (CACHE) timestamp of computation creation
    raw_data_path (str | None): (CACHE) path to raw data file, if any
    renders (dict[str, ImageData]): (CHILDREN) one computation can have multiple renders;
        dict of {render_hash: ImageData}

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # CORE DATA: Frame + ComputationParameters = a specific computation
  frm: str  # Frame hash (frame_hash)
  cp: str  # ComputationParameters hash (cp_hash) - look in _DBType.cps

  # CACHE: the raw data is the most expensive to compute, so we store it
  tm: int  # timestamp of last time this image was rendered; if we have the entry, we must have tm
  raw_data_path: str | None  # path to raw data file; BEWARE: relative path, managed by DB!

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


CoreKeyFromData: abc.Callable[
  [frame.ComputationParameters, image.RenderParameters], ImageCoreKey
] = lambda c, r: ImageCoreKey(frm=c.frm.sha, cp=c.sha, render=r.sha)


class ImageData(TypedDict):
  """Image data type, for storing PNG image/frame metadata and parameters. CANNOT be a video/GIF.

  Attributes:
    core (ImageCoreKey): (CORE DATA) the 3 hashes that uniquely identify an image: frame_hash,
        cp_hash, and render_hash
    data_hash (str): (CACHE) hash of the image PNG data; if we have this entry,
        we must have the hash!
    tm (int): (CACHE) timestamp of rendered image last creation
    rendered_paths (list[str]): (CACHE) paths to renders of this image PNG; presumably identical

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # CORE DATA: Frame + ComputationParameters + RenderParameters = a specific PNG image
  core: ImageCoreKey  # we nest the core data

  # CACHE
  data_hash: str  # hash of the image PNG data - BEWARE: this hash is POST-render but PRE-overlay!!
  tm: int  # timestamp of last time this image was rendered; if we have data_hash, we must have tm
  rendered_paths: list[str]  # paths to image PNG files; empty if not saved (actual path on disk)


class ZoomData(TypedDict):
  """Video/GIF zoom data type, for storing zoom metadata and parameters.

  Attributes:
    zoom (tbase.JSONDict): (CORE DATA) image.ZoomParameters.json; note that zoom is created
        with the sentinel value (if on AUTO) and does NOT update!
    fps (float): (CACHE) frames-per-second; number of total frames is exactly len(frames)
    step_mag (float): (CACHE) video step scalar magnification (magnification per frame step)
    data_hash (str): (CACHE) hash of the video/GIF data; if we have this entry,
        we must have the hash!
    tm (int): (CACHE) timestamp of last rendered video/GIF creation
    rendered_path (str | None): (CACHE) path to video/GIF file; None if not saved
    frames (list[str]): ("CHILDREN") list of Frame hashes -> grandfather Frames; ordered by
        magnification ascending; len >=3
    markers (list[tuple[int, str]]): ("CHILDREN") subset of frames entry: key Frame(s) for color
        normalization; (idx, Frame) and idx is the index in the frames list; len >=2 (first & last)

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.

  """

  # CORE DATA: ZoomParameters = a specific video, the rest is computed
  zoom: tbase.JSONDict  # image.ZoomParameters.json; has original sentinel value (if on AUTO)

  # CACHE
  fps: float  # = len(`frames`) / `zoom.duration`
  step_mag: float  # video step SCALAR magnification (total magnitude is in `zoom.mag`)
  data_hash: str  # hash of the video/GIF data = SHA-256('|'.join(data_hash for all frames))
  tm: int  # timestamp of last rendered video/GIF creation
  rendered_path: str | None  # path to video/GIF file; None if not saved

  # "CHILDREN" would be the individual frames/images that compose the video;
  # we compute this from core data, so this could be "CACHE" too...
  frames: list[str]  # Frame hashes; ordered by magnification ascending; len >=3
  markers: list[tuple[int, str]]  # subset of frames entry: key Frame(s); len >=2 (first & last)


class _DBType(TypedDict):
  """DB object type.

  Attributes:
    db_version (int): DB version; increment on save
    app_version (str): package version (tranzoom.__version__) at time of last save
    last_save (int): timestamp of last save
    frames (dict[str, FrameData]): {frame_hash: FrameData}
    cps (dict[str, tbase.JSONDict]): {cp_hash: frame.ComputationParameters.json}
    renders (dict[str, tbase.JSONDict]): {render_hash: image.RenderParameters.json}
    videos (dict[str, ZoomData]): {video_hash: ZoomData}, video_hash is the ZoomData.sha hash!
    sentinel_cps_idx (dict[str, str]): {cp_hash: cp_hash} depth lookup, maps sentinel cp_hash,
        that has fixed depth=1000, to the final cp_hash with actual depth; this allows us to
        quickly find the actual computation parameters for a given sentinel, which is what we use
    img_paths_idx (dict[str, ImageCoreKey]): {img_path: ImageCoreKey} for easy lookup of PNG paths
    video_paths_idx (dict[str, str]): {video_path: video_hash} for easy lookup of GIF/video paths
    images_idx (dict[str, list[ImageCoreKey]]): {data_hash: [im1, im2, ...]} for lookup of images by
        their data hash; since the hash is PRE-overlay, we might have multiple obj with same hash
    videos_idx (dict[str, list[str]]): {data_hash: [video_hash1, video_hash2, ...]} for lookup by
        their data hash; since the hash is PRE-overlay, we might have multiple obj with same hash

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

  # internal indexes: for fast lookup of data based on known keys
  sentinel_cps_idx: dict[str, str]  # {cp_hash: cp_hash} depth lookup, from sentinel 1000 to actual

  # path indexes: from known image/video on-disk paths -> core data key entries
  img_paths_idx: dict[str, ImageCoreKey]  # {img_path: ImageCoreKey} for easy lookup of PNG paths
  video_paths_idx: dict[str, str]  # {video_path: video_hash} for easy lookup of GIF/video paths

  # data_hash indexes: since the hash is PRE-overlay, we might have multiple obj with the same hash
  images_idx: dict[str, list[ImageCoreKey]]  # {data_hash: [im1, im2, ...]}
  videos_idx: dict[str, list[str]]  # {data_hash: [video_hash1, video_hash2, ...]}


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
    'sentinel_cps_idx': {},
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
    use_db: bool = True,
    read_only: bool = False,
    aes_key: aes.AESKey | None = None,
    safe_save: bool = True,
    compress_save: bool = False,
    format_json: bool = True,
  ) -> None:
    """Initialize the fractal database.

    Args:
      appconfig (app_config.AppConfig): AppConfig object for configuration and directory management.
      use_db (bool): Whether to use the database functionality; if False, the DB will behave as if
          it does not exist
      read_only (bool): If True, the database will be opened in read-only mode; default is
          False, meaning it can be read and written to; if True, any attempt to write to the DB
          will raise an error.
      aes_key (aes.AESKey | None): (default None) Optional AES key for encrypting/decrypting the
          database file
      safe_save (bool): (default True) Whether to use a safe save method that reads the existing
          DB file before writing, to prevent data loss from clobbering; if False, it will
          overwrite the file directly
      compress_save (bool): (default False) Whether to compress the DB file when saving; if True,
          it will save as a compressed file; NOTE: if you provide an AES key, the DB will always be
          compressed regardless of this option
      format_json (bool): (default True) Whether to format the JSON output with indentation
          for readability; NOTE: if an AES key is provided, this is always treated as False
          (compact JSON) to avoid leaking whitespace patterns before encryption.

    Raises:
      Error: if another instance of FractalDatabase is already open

    """
    self._config: app_config.AppConfig = appconfig
    self._path: pathlib.Path = self._config.dir / _DB_FILE_NAME
    self._use_db: bool = use_db
    self._read_only: bool = read_only
    self._key: aes.AESKey | None = aes_key
    self._safe_save: bool = safe_save
    self._compress_save: bool = compress_save or (aes_key is not None)  # always compress if encrypt
    self._format_json: bool = format_json and (aes_key is None)  # never pretty-print if encrypting
    self._db: _DBType = _DBTypeFactory()  # always populate the variable for safety and sanity
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
    logging.info(
      f'FractalDatabase initialized: {self.label}, {self._use_db=}, {self._read_only=}, '
      f'{"ENCRYPTED, " if self._key else ""}{self._safe_save=}, '
      f'{self._compress_save=}, {self._format_json=}'
    )

  def _InitLoad(self) -> None:
    """Load the database from disk (or create a new one). Called only from __init__().

    Raises:
      Error: if the DB file is possibly encrypted and no AES key is provided
      UnicodeDecodeError: on error

    """
    if not self._use_db:
      logging.warning('use_db is False: will not load DB and will work as if DB does not exist!')
      return
    with _DB_DISK_LOCK:  # ensure thread-safe load operations
      if self._path.exists():
        try:
          self._db = cast(
            '_DBType',
            self._config.DeSerialize(
              config_name=_DB_FILE_NAME, decryption_key=self._key, unpickler=key.UnpickleJSON
            ),
          )
          logging.info(f'Loaded DB from "{self._path}": {self.label}')
        except UnicodeDecodeError as err:
          if 'invalid start byte' in str(err):
            raise Error('This is possibly an ENCRYPTED DB file: use option `--pass`?') from err
          raise
      else:
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
    if not self._use_db:
      logging.warning('use_db is False: no DB to close, skipping save')
      FractalDatabase._CONTEXT_LOCK.release()
      return
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
      str: A human-readable label string of the form '#<N>@<tm>'.

    """
    return _DBLabel(self._db)

  def Save(self) -> None:
    """Save the database to file.

    Raises:
      Error: if safe_save is enabled and the existing DB on disk differs from the loaded DB

    """
    if self._read_only or not self._use_db:
      logging.warning('DB in read-only mode or use_db is False: will *NOT* save! (would have now)')
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

  def SaveImageData(
    self, params: frame.ComputationParameters, img: image.Image
  ) -> tuple[int, str | None]:
    """Save image data to disk.

    Args:
      params (frame.ComputationParameters): the computation parameters associated with the image
      img (image.Image): the image data to save

    Returns:
      tuple[int, str | None]: a tuple containing the timestamp and the path where the image
          data was saved, or None if in read-only mode

    """
    path: str = f'img_{params.sha}.Data'
    # trivial case first
    if self._read_only or not self._use_db:
      logging.warning(f'Read-only mode or use_db is False: will *NOT* save {params} to {path!r}')
      return (timer.Now(), None)
    # we don't want to save histograms!
    ext_hist: image.Image.Histogram | None = img.ext_hist
    int_hist: image.Image.Histogram | None = img.int_hist
    try:
      img.ext_hist, img.int_hist = None, None
      # we will actually save
      self._config.Serialize(
        img,
        config_name=path,
        encryption_key=self._key,
        compress=_IMG_DATA_COMPRESS_LEVEL,
        silent=True,
      )
      logging.info(f'Saved image data {params} to {path!r}, {human.HumanizedBytes(img.self_sz)}')
    finally:
      # restore histograms in case the caller needs them after saving
      img.ext_hist, img.int_hist = ext_hist, int_hist
    return (timer.Now(), path)

  def LoadImageData(self, path: str) -> image.Image | None:
    """Load image data from disk.

    Args:
      path (str): relative path to the image data file, as stored in the DB; this is a relative path
        managed by the DB, not an arbitrary path; the actual path on disk is self._config.dir / path

    Returns:
      image.Image | None: the loaded image data, or None only if use_db is False

    """
    if not self._use_db:
      logging.debug('use_db is False: skipping loading image computation')
      return None
    img: image.Image = self._config.DeSerialize(
      config_name=path, decryption_key=self._key, silent=True
    )
    img.RebuildHistograms()  # histograms are not saved, so we need to rebuild them after loading
    return img

  def FindComputation(
    self, params: frame.ComputationParameters
  ) -> tuple[frame.ComputationParameters, FrameData | None, ComputationData | None]:
    """Find a computation in the database given its parameters.

    Args:
      params (frame.ComputationParameters): the computation parameters associated with the image

    Returns:
      tuple[
          frame.ComputationParameters, FrameData | None, ComputationData | None]: a tuple containing
          the ComputationParameters, and the corresponding FrameData and ComputationData if found;
          if not found, the missing entries will be None; we have to return params because
          it could have been replaced with one with the "real" depth

    Raises:
      Error: on error, mostly inconsistent DB, not missing data

    """
    if not self._use_db:
      logging.debug('use_db is False: skipping computation lookup')
      return (params, None, None)
    # first check: do we know this computation? it could be a sentinel with depth=1000
    cp_hash: str = params.sha
    if params.depth == frame.MIN_ITER and cp_hash in self._db['sentinel_cps_idx']:
      # this is a sentinel
      orig_hash: str = cp_hash
      cp_hash = self._db['sentinel_cps_idx'][cp_hash]
      if cp_hash not in self._db['cps']:
        raise Error(f'Inconsistent DB: found sentinel {cp_hash=!r} but not in cps; Report bug!')
      # update depth
      params = dataclasses.replace(params, depth=cast('int', self._db['cps'][cp_hash]['depth']))
      logging.debug(f'sentinel resolved to actual {orig_hash=!r} -> {cp_hash=!r}')
      if params.sha != cp_hash:
        raise Error(f'Sentinel {orig_hash=!r} -> {cp_hash=!r} but {params.sha=!r}; Report bug!')
    # now we can check if we have the computation parameters
    if cp_hash not in self._db['cps']:
      # we don't even know the computation parameters, so we definitely don't have the image
      return (params, None, None)
    # we know the computation parameters: get it
    frm_hash: str = params.frm.sha
    if frm_hash not in self._db['frames']:
      raise Error(f'Inconsistent DB: found {cp_hash=!r} but not {frm_hash=!r}; Report bug!')
    frm_data: FrameData = self._db['frames'][frm_hash]
    if cp_hash not in frm_data['cps']:
      raise Error(f'Inconsistent DB: found {cp_hash=!r} in DB but not in frame data; Report bug!')
    return (params, frm_data, frm_data['cps'][cp_hash])

  def FindRender(
    self, params: frame.ComputationParameters, render: image.RenderParameters
  ) -> tuple[
    frame.ComputationParameters,
    ImageCoreKey,
    FrameData | None,
    ComputationData | None,
    ImageData | None,
  ]:
    """Find an image in the database given its computation parameters and render parameters.

    Args:
      params (frame.ComputationParameters): the computation parameters associated with the image
      render (image.RenderParameters): the render parameters associated with the image

    Returns:
      tuple[
          frame.ComputationParameters, ImageCoreKey, FrameData | None, ComputationData | None,
          ImageData | None]: a tuple containing the ComputationParameters, ImageCoreKey,
          and the corresponding FrameData, ComputationData, and ImageData if found;
          if not found, the missing entries will be None; we have to return params because
          it could have been replaced with one with the "real" depth

    Raises:
      Error: on error, mostly inconsistent DB, not missing data

    """
    if not self._use_db:
      logging.debug('use_db is False: skipping render lookup')
      return (params, CoreKeyFromData(params, render), None, None, None)
    # check computation... and maybe have a renewed param with the correct depth
    frm_data: FrameData | None
    cp_data: ComputationData | None
    params, frm_data, cp_data = self.FindComputation(params)
    # build the core key for this image now that we have the finalized param
    ck: ImageCoreKey = CoreKeyFromData(params, render)
    # did we get stuff back? if not we can stop here... or maybe we don't have the render?
    if not frm_data or not cp_data or ck['render'] not in cp_data['renders']:
      # we don't even know the computation parameters, so we definitely don't have the image
      return (params, ck, frm_data, cp_data, None)  # but we return what we do have...
    # we know the render parameters: get it and return
    if (render_hash := ck['render']) not in self._db['renders']:
      raise Error(f'Inconsistent DB: found {render_hash=!r} in DB but not in renders; Report bug!')
    return (params, ck, frm_data, cp_data, cp_data['renders'][render_hash])

  def FindZoom(self, zoom: image.ZoomParameters) -> ZoomData | None:
    """Find a zoom (video/GIF) in the database given its zoom parameters.

    Args:
      zoom (image.ZoomParameters): the zoom parameters to look up

    Returns:
      ZoomData | None: the ZoomData for the given zoom parameters, or None if not found

    """
    if not self._use_db:
      logging.debug('use_db is False: skipping zoom lookup')
      return None
    # videos are keyed directly by zoom.sha; one hash -> one ZoomData entry (no indirection)
    return self._db['videos'].get(zoom.sha)

  def AddComputationToDB(
    self, params: frame.ComputationParameters, img_tm: int, img_path: str | None
  ) -> tuple[FrameData | None, ComputationData | None]:
    """Add a computation to the database, along with its associated frame if not already present.

    Args:
      params (frame.ComputationParameters): the computation parameters to add
      img_tm (int): the timestamp of the associated image data creation
      img_path (str | None): the path to the associated image data file, as stored in the DB;
          this is a relative path managed by the DB, not an arbitrary

    Returns:
      tuple[FrameData | None, ComputationData | None]: the FrameData and ComputationData objects
          corresponding; will ONLY return None if use_db is False

    """
    if not self._use_db:
      logging.info('use_db is False: skipping add computation to DB')
      return (None, None)
    # add frame
    frm_hash: str = params.frm.sha
    frm: FrameData
    if frm_hash in self._db['frames']:
      frm = self._db['frames'][frm_hash]
    else:
      frm = FrameData(
        frm=params.frm.json,
        mag=params.frm.magnification[1],
        cps={},
      )
      self._db['frames'][frm_hash] = frm
      logging.info(f'AddComputationToDB: new frame {frm_hash!r} added to DB')
    # add computation
    cp_hash: str = params.sha
    if cp_hash not in self._db['cps']:
      self._db['cps'][cp_hash] = params.json
    cp: ComputationData
    if cp_hash in frm['cps']:
      cp = frm['cps'][cp_hash]
      if img_path is not None:
        cp['tm'] = img_tm  # update timestamp if we saved a file only, in case of update
        cp['raw_data_path'] = img_path  # if given, update path (in case it changed: unlikely)
    else:
      cp = ComputationData(
        frm=frm_hash,
        cp=cp_hash,
        tm=img_tm,
        raw_data_path=img_path,
        renders={},
      )
      frm['cps'][cp_hash] = cp
      logging.info(f'AddComputationToDB: new computation {cp_hash!r} added to DB')
    # add sentinel index, if needed
    if params.depth > frame.MIN_ITER:
      # depth > 1000 means we should add to the index, so we can find this later
      sentinel_cp: frame.ComputationParameters = dataclasses.replace(params, depth=frame.MIN_ITER)
      self._db['sentinel_cps_idx'][sentinel_cp.sha] = cp_hash
    # return the FrameData / ComputationData
    return (frm, cp)

  def AddRenderToDB(
    self,
    params: frame.ComputationParameters,
    render: image.RenderParameters,
    ck: ImageCoreKey,
    img_hash: str,
    path: str,
  ) -> ImageData | None:
    """Add a render to the DB, along with associated frame, computation, indexes if not present.

    Args:
      params (frame.ComputationParameters): the computation parameters associated with the render
      render (image.RenderParameters): the render parameters to add
      ck (ImageCoreKey): the core key for the image, containing the frame_hash, cp_hash, render_hash
      img_hash (str): the hash of the image PNG data, used for indexing and deduplication
      path (str): the path to the image PNG file, as stored in the DB; this is absolute disk path

    Returns:
      ImageData | None: the ImageData object corresponding to the added render; will ONLY return
          None if use_db is False

    Raises:
      Error: on error, mostly inconsistent DB, not missing data

    """
    if not self._use_db:
      logging.info('use_db is False: skipping add render to DB')
      return None
    # get frame and computation
    frm_hash: str = params.frm.sha
    if frm_hash not in self._db['frames']:
      raise Error(f'Inconsistent DB: frame_hash {frm_hash!r} not found in DB frames; Report bug!')
    frm: FrameData = self._db['frames'][frm_hash]
    cp_hash: str = params.sha
    if cp_hash not in self._db['cps'] or cp_hash not in frm['cps']:
      raise Error(f'Inconsistent DB: cp_hash {cp_hash!r} not found in DB cps; Report bug!')
    cp: ComputationData = frm['cps'][cp_hash]
    # add render
    render_hash: str = render.sha
    if render_hash not in self._db['renders']:
      self._db['renders'][render_hash] = render.json
    img: ImageData
    if render_hash in cp['renders']:
      img = cp['renders'][render_hash]
      img['tm'] = timer.Now()  # always update timestamp
      existing: list[str] = ExistingPathsFilter(img['rendered_paths'])
      # BEWARE: path not saved yet! (so not existing) but we could be re-rendering to the same path
      img['rendered_paths'] = existing if path in existing else [*existing, path]
    else:
      img = ImageData(
        core=ck,
        data_hash=img_hash,
        tm=timer.Now(),
        rendered_paths=[path],
      )
      cp['renders'][render_hash] = img
      logging.info(f'AddRenderToDB: new render {render_hash!r} added to DB, path {path!r}')
    # add path index
    self._db['img_paths_idx'][path] = ck
    # add hash index
    idx_list: list[ImageCoreKey] = self._db['images_idx'].setdefault(img_hash, [])
    if ck not in idx_list:
      idx_list.append(ck)
    # return the new ImageData
    return img

  def AddZoomToDB(
    self,
    zoom: image.ZoomParameters,
    data_hash: str,
    tm: int,
    path: str,
    all_frames: list[frame.Frame],
    markers: list[tuple[int, frame.Frame]],
  ) -> None:
    """Add a zoom (video/GIF) to the DB.

    Args:
      zoom (image.ZoomParameters): the zoom parameters to add; zoom is created with the sentinel
          value (if on AUTO) and does NOT update!
      data_hash (str): the hash of the video/GIF data, used for indexing and deduplication
      tm (int): the timestamp of the video/GIF creation
      path (str): the path to the video/GIF file, as stored in the DB; this is absolute disk path
      all_frames (list[frame.Frame]): the list of all frames that compose the video, ordered by
          magnification ascending (video order)
      markers (list[tuple[int, frame.Frame]]): the marker frames that compose the video, a
          subset of all_frames

    Raises:
      Error: on error, mostly inconsistent DB, not missing data

    """
    if not self._use_db:
      logging.info('use_db is False: skipping add zoom to DB')
      return
    # videos are keyed directly by zoom.sha; one hash -> one ZoomData entry (no indirection)
    zoom_hash: str = zoom.sha
    if zoom_hash in self._db['videos']:
      # we have an entry: we assume it is mostly correct, but update the path
      self._db['videos'][zoom_hash]['tm'] = tm  # always update timestamp
      self._db['videos'][zoom_hash]['rendered_path'] = path  # update path (in case it changed)
      logging.info(f'AddZoomToDB: updated existing zoom {zoom_hash!r} in DB, path {path!r}')
    else:
      # new entry
      zd: ZoomData = ZoomData(
        zoom=zoom.json,
        fps=float(zoom.fps),
        step_mag=float(zoom.scalar_magnification_per_step),
        data_hash=data_hash,
        tm=tm,
        rendered_path=path,
        frames=[f.sha for f in all_frames],
        markers=[(j, f.sha) for j, f in markers],
      )
      if any(1 for j, f in zd['markers'] if zd['frames'][j] != f):
        raise Error('Inconsistent DB: marker frame hashes do not match frames list; Report bug!')
      self._db['videos'][zoom_hash] = zd
      logging.info(
        f'AddZoomToDB: new zoom {zoom_hash!r} added to DB, '
        f'{len(all_frames)} frames, {len(markers)} markers, path {path!r}'
      )
    # add path index
    self._db['video_paths_idx'][path] = zoom_hash
    # add hash index
    idx_list: list[str] = self._db['videos_idx'].setdefault(data_hash, [])
    if zoom_hash not in idx_list:
      idx_list.append(zoom_hash)

  def CoreComputeImage(
    self,
    params: frame.ComputationParameters,
    render: image.RenderParameters,
    out: image.ImageOutputConfig,
    add_serial: int | None,
    tm: int | None,
    max_threads: int | None,
    iterm: bool,
    print_comm: abc.Callable[[str], None],
    *,
    force: bool = False,
  ) -> tuple[frame.ComputationParameters, image.Image | None, bytes, str, pathlib.Path]:
    """Compute a fractal image and return the result unsaved; the shared rendering primitive.

    This operates even if use_db is False and read_only is True, it just won't use/save cache...

    This is the shared image computation primitive used by all rendering paths (static images,
    AI-guided zoom, manual zoom, and animations). It does NOT save the image to disk — the
    caller decides when and how to save, allowing callers to add evaluation metadata first.

    Note: the content hash is computed from the raw PNG before any post-processing overlays
    (crosshair mark, sector grid). The saved bytes contain all overlays; the hash is used for
    deduplication and file naming.

    Args:
      params (frame.ComputationParameters): The computation parameters for the frame, including
          width, height, and other settings.
      render (image.RenderParameters): The render parameters, including color palettes, optional
          crosshair mark (mark_color not None means draw a crosshair), and optional sector overlay
          (overlay not None means draw the numbered sector grid).
      out (image.ImageOutputConfig): Output path configuration for building the file name.
      add_serial (int | None): Optional serial number for the file name (zoom step numbering);
          None means no serial number is added.
      tm (int | None): Optional fixed timestamp for the file name (zoom session consistency);
          None means the current wall-clock time is used.
      max_threads (int | None): Maximum threads for parallel rendering; None means all CPUs.
      iterm (bool): If True, print the image inline in iTerm2 after rendering.
      print_comm (abc.Callable[[str], None]): A rich console callable for printing messages.
      force (bool): If True, will force re-computation of the image even if it is found in the DB

    Returns:
      tuple[frame.ComputationParameters, image.Image | None, bytes, str, pathlib.Path]: A 5-tuple:
          - frame.ComputationParameters: The computation parameters used for the frame
              (with actual depth if a sentinel was used)
          - image.Image: the computed fractal Image object
          - bytes: the final PNG bytes (with crosshair mark and sector overlay applied, if any)
          - str: the SHA-256 hash of the raw PNG before any post-processing overlays
          - pathlib.Path: the intended save path (NOT yet written to disk; caller must save)

    Raises:
      Error: on error

    """
    # check parameters
    if (render.set_pal is not None and params.set_points is None) or (
      render.set_pal is None and params.set_points is not None
    ):
      raise Error(
        'Cannot specify set_pal without set_points; set_points is required to use set_pal'
      )
    # computation
    img: image.Image
    params, img = self.DoComputation(params, max_threads, print_comm, force=force)
    print_comm('')
    # render
    return (
      params,
      img,
      *self.DoRender(
        img,
        render,
        out,
        add_serial,
        tm,
        iterm,
        print_comm,
        force=force,
      ),
    )

  def DoComputation(
    self,
    params: frame.ComputationParameters,
    max_threads: int | None,
    print_comm: abc.Callable[[str], None],
    *,
    force: bool = False,
  ) -> tuple[frame.ComputationParameters, image.Image]:
    """Compute a fractal, producing an image.Image.

    This operates even if use_db is False and read_only is True, it just won't use/save cache...

    Args:
      params (frame.ComputationParameters): The computation parameters for the frame, including
          width, height, and other settings.
      max_threads (int | None): Maximum threads for parallel rendering; None means all CPUs.
      print_comm (abc.Callable[[str], None]): A rich console callable for printing messages.
      force (bool): If True, will force re-computation of the image even if it is found in the DB

    Returns:
      tuple[frame.ComputationParameters, image.Image]: A tuple:
          - frame.ComputationParameters: The computation parameters used for the frame
              (with actual depth if a sentinel was used)
          - image.Image: the computed fractal Image object

    """
    # log
    set_param: str = '' if params.set_points is None else f' w/ SET {params.set_points.value!r}'
    print_comm(
      f'{params.width} x {params.height} '
      f'{params.frm.fractal.value.capitalize()}{set_param}, '
      f'10^{params.frm.magnification[1]:.3f} magnitude...'
    )
    print_comm(f'[yellow]Compute:[/] {params}')
    # do we know about this render?
    img: image.Image | None = None
    img_path: str | None = None
    img_tm: int | None = None
    cp_data: ComputationData | None
    params, _, cp_data = self.FindComputation(params)
    # do we know about this computation?
    if cp_data is not None:
      # we have done a render with these parameters before
      img_tm = cp_data['tm']
      if (img_path := cp_data['raw_data_path']) is not None:
        # second best case: we have the image computation on disk already
        print_comm(f'[red]DB computation[/] LOAD @{timer.TimeStr(img_tm)} -> "{img_path}"')
        try:
          img = None if force else self.LoadImageData(img_path)
        except tbase.InputError as err:
          print_comm(f'[red]DB computation MISSING[/]: {err}')
      else:
        # we have done the computation but do not have the data on disk
        print_comm(f'[red]DB computation[/] @{timer.TimeStr(img_tm)} -> [red]no cache on disk[/]')
    else:
      logging.debug('DB miss: no computation data')
    # render the image for the current frame
    tmr: timer.Timer | None = None
    if img is None or img_path is None or img_tm is None:
      with timer.Timer(emit_log=False) as tmr:
        params, img = fractal.ComputeFractal(
          params,  # remember that this params will be updated with the actual depth now!
          progress_bar=True,
          n_processes=max_threads,
          print_comm=print_comm,
        )
        # save img in DB & disk
        img_tm, img_path = self.SaveImageData(params, img)  # disk only
        self.AddComputationToDB(params, img_tm, img_path)  # DB only; returns None if use_db==False
    # done: log and return
    print_comm(
      f'[yellow]Compute:[/] [green]{params.frm.fractal.value.capitalize()}: DONE,[/] '
      f'with precision {params.precision} bits, {human.HumanizedBytes(img.self_sz)}, '
      f'in {str(tmr) if tmr else "-"}'
    )
    return (params, img)

  def DoRender(
    self,
    img: image.Image,
    render: image.RenderParameters,
    out: image.ImageOutputConfig,
    add_serial: int | None,
    tm: int | None,
    iterm: bool,
    print_comm: abc.Callable[[str], None],
    *,
    force: bool = False,
    zoom_norm: image.Image.FrameColorNorm | None = None,
    silent: bool = False,
    no_meta: bool = False,
  ) -> tuple[bytes, str, pathlib.Path]:
    """Take an image.Image and do the fractal rendering.

    This operates even if use_db is False and read_only is True, it just won't use/save cache...

    Note: the content hash is computed from the raw PNG before any post-processing overlays
    (crosshair mark, sector grid). The saved bytes contain all overlays; the hash is used for
    deduplication and file naming.

    Args:
      img (image.Image): The computed fractal Image object.
      render (image.RenderParameters): The render parameters, including color palettes, optional
          crosshair mark (mark_color not None means draw a crosshair), and optional sector overlay
          (overlay not None means draw the numbered sector grid).
      out (image.ImageOutputConfig): Output path configuration for building the file name.
      add_serial (int | None): Optional serial number for the file name (zoom step numbering);
          None means no serial number is added.
      tm (int | None): Optional fixed timestamp for the file name (zoom session consistency);
          None means the current wall-clock time is used.
      iterm (bool): If True, print the image inline in iTerm2 after rendering.
      print_comm (abc.Callable[[str], None]): A rich console callable for printing messages.
      force (bool): If True, will force re-computation of the image even if it is found in the DB
      zoom_norm (image.Image.FrameColorNorm | None): Optional color normalization parameters to use
          for zoom rendering; if None, the default normalization is used; this is only used for
          zoom rendering, and is ignored for static image rendering
      silent (bool): If True, will suppress all printing output from this function; if False, will
          redirect output to logging.info logs; default is False
      no_meta (bool): If True, do not include metadata in the PNG; mainly for video frames where
          metadata is not needed and adds overhead. Default is False (include metadata).

    Returns:
      tuple[bytes, str, pathlib.Path]: A tuple:
          - bytes: the final PNG bytes (with crosshair mark and sector overlay applied, if any)
          - str: the SHA-256 hash of the raw PNG before any post-processing overlays
          - pathlib.Path: the intended save path (NOT yet written to disk; caller must save)

    Raises:
      Error: on error

    """
    print_comm = logging.info if silent else print_comm
    # check parameters
    if (render.set_pal is not None and img.params.set_points is None) or (
      render.set_pal is None and img.params.set_points is not None
    ):
      raise Error(
        'Cannot specify set_pal without set_points; set_points is required to use set_pal'
      )
    # log
    print_comm(f'[yellow]Render:[/] {render}')
    # create path callback missing only the hash
    full_path: abc.Callable[[str], pathlib.Path] = lambda h: image.MakeImagePath(
      out.path,
      out.use_date,
      out.use_hash,
      out.prefix,
      h,
      tm=tm,
      add_serial=add_serial,
    )
    # do we know about this render?
    ck: ImageCoreKey
    img_hash: str
    img_data: bytes
    render_data: ImageData | None
    params: frame.ComputationParameters
    params, ck, _, _, render_data = self.FindRender(img.params, render)
    if params != img.params:
      raise Error('Render computation parameters do not match image parameters; Report bug!')
    # look at the actual render
    if render_data is not None:
      # we have done a render with these parameters before
      if (
        not force and self._use_db and (paths := ExistingPathsFilter(render_data['rendered_paths']))
      ):
        # best case: we have the image PNG on disk already
        # take the first existing path, we know we have at least one
        path: pathlib.Path = pathlib.Path(paths[0])
        print_comm(
          f'[red]DB render[/], {render_data["data_hash"]!r}@{timer.TimeStr(render_data["tm"])} '
          f'-> "{path}"'
        )
        img_hash = render_data['data_hash']
        img_data = path.read_bytes()  # this is why we guard against self._use_db/force
        # we can end this: we have the image PNG on disk and img is as good as necessary
        print_comm(
          f'[yellow]Render:[/] [green]{render.tp.value.upper()}: DONE,[/] {img_hash!r} in -'
        )
        # print inline in iTerm2 if requested
        if iterm:
          print_comm('')
          image.PrintITerm2(img_data)
        return (img_data, img_hash, full_path(img_hash))
      # if we got here, we have the render parameters but no existing image on disk
      print_comm(
        f'[red]DB render[/], {render_data["data_hash"]!r}@{timer.TimeStr(render_data["tm"])} '
        f'-> [red]no disk[/]'
      )
    else:
      logging.debug('DB miss: no render data')
    # we got to here, so we have to render the PNG data from the image object and add overlay/mark;
    # hash is computed from the raw PNG before any post-processing overlays
    with timer.Timer(emit_log=False) as tmr:
      img_data, img_hash = img.AsPNG(  # <<== this is the actual render!
        render, zoom_norm=zoom_norm, no_meta=no_meta
      )
      # draw crosshair mark if specified in render parameters
      if render.mark_color is not None:
        _, mark_pixel = params.CoordToPixel(render.mark_re, render.mark_im)
        print_comm(
          f'[cyan]Marking[/] coordinate ({render.mark_re}, {render.mark_im}) with '
          f'{render.mark_color.name.lower()!r} crosshair @{mark_pixel}/{render.mark_width}px'
        )
        img_data = image.DrawCrossOverlay(
          img_data, *mark_pixel, col=render.mark_color, lw=render.mark_width
        )
      # draw the numbered sector grid overlay if requested (e.g., for AI/manual zoom navigation)
      if render.overlay is not None:
        print_comm(f'[cyan]Adding[/] {render.overlay.value!r} overlay')
        if render.overlay == image.OverlayType.GRID:
          img_data = image.DrawThirdsInfoOverlay(img_data)
        else:
          raise Error(f'Unsupported overlay type: {render.overlay!r}')
      # add to DB; remember render_data could be None if use_db==False
      render_data = self.AddRenderToDB(params, render, ck, img_hash, str(full_path(img_hash)))
    # log
    print_comm(
      f'[yellow]Render:[/] [green]{render.tp.value.upper()}: DONE,[/] {img_hash!r} '
      f'in {tmr}, {human.HumanizedBytes(len(img_data))}'
    )
    # print inline in iTerm2 if requested
    if iterm:
      print_comm('')
      image.PrintITerm2(img_data)
    return (img_data, img_hash, full_path(img_hash))


def _DBLabel(db: _DBType) -> str:
  """Get a human-readable label for the database, for logging and display purposes.

  Args:
    db (_DBType): The database object to get the label for.

  Returns:
    str: string '#<N>@<tm>'

  """
  return f'#{db["db_version"]}@{timer.TimeStr(db["last_save"])}'
