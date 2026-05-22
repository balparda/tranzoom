# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal Database core logic."""

from __future__ import annotations

import logging
import threading
from typing import Self, TypedDict, cast

from transcrypto.core import aes, key
from transcrypto.utils import base as tbase
from transcrypto.utils import config as app_config
from transcrypto.utils import timer

from tranzoom import __version__
from tranzoom.core import fractal

# DB constants

_DB_COMPRESS_LEVEL = 5  # default compression level for DB saving
_DB_DISK_LOCK: threading.Lock = threading.Lock()  # lock for thread-safe DB operations


class Error(fractal.Error):
  """Base fractal database exception."""


class _DBType(TypedDict):
  """DB object type.

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.
  """

  db_version: int  # DB version; increment on save
  app_version: str  # package version (tranzoom.__version__) at time of last save
  last_save: int  # timestamp of last save
  # TODO: we have to add data


def _DBTypeFactory(overrides: dict[str, object] | None = None) -> _DBType:
  """Create new _DBType object with default values.

  Args:
    overrides: dict of fields to override from the defaults; if None, will use all defaults

  Returns:
    A new _DBType object with default values.

  """
  obj: _DBType = {
    'db_version': 0,
    'app_version': __version__,  # set to current package version on creation
    'last_save': timer.Now(),
  }
  obj.update(overrides or {})  # type: ignore[typeddict-item]
  return obj


class FractalDatabase:
  """Fractal database class, for storing and retrieving frames/images and their metadata."""

  def __init__(
    self,
    appconfig: app_config.AppConfig,
    *,
    read_only: bool = False,
    aes_key: aes.AESKey | None = None,
    safe_save: bool = True,
    compress_save: bool = False,
  ) -> None:
    """Initialize the fractal database.

    Args:
      appconfig: AppConfig object for configuration and directory management.
      read_only: If True, the database will be opened in read-only mode; default is
          False, meaning it can be read and written to; if True, any attempt to write to the DB
          will raise an error.
      aes_key: (default None) Optional AES key for encrypting/decrypting the database file
      safe_save: (default True) Whether to use a safe save method that reads the existing DB file
          before writing, to prevent data loss from clobbering; if False, it will overwrite
          the file directly
      compress_save: (default False) Whether to compress the DB file when saving; if True, it will
          save as a compressed file

    """
    self._config: app_config.AppConfig = appconfig
    self._read_only: bool = read_only
    self._key: aes.AESKey | None = aes_key
    self._safe_save: bool = safe_save
    self._compress_save: bool = compress_save
    self._db: _DBType
    self._open = timer.Timer('FractalDatabase', emit_log=False)
    with _DB_DISK_LOCK:  # ensure thread-safe load operations
      if self._config.path.exists():
        self._db = cast(
          '_DBType', self._config.DeSerialize(decryption_key=self._key, unpickler=key.UnpickleJSON)
        )
        logging.info(f'Loaded DB from {self._config.path}: {self.label}')
      else:
        self._db = _DBTypeFactory()
        logging.warning(f'DB file not found, will start fresh, {self.label}')
    if self._read_only:
      logging.warning('ATTENTION: Database opened in read-only mode, changes will not be saved!')

  def __enter__(self) -> Self:
    """Context manager entry, returns self.

    Returns:
      self, for use within the context

    """
    return self

  def __exit__(
    self,
    exc_type: type[BaseException] | None,
    _exc_value: BaseException | None,
    _traceback: object,
  ) -> None:
    """Context manager exit. If not exception, saves the database to file.

    Args:
      exc_type: exception type, if any
      _exc_value: exception value, if any
      _traceback: traceback object, if any

    """
    logging.info(f'Database was open for {self._open}')
    if exc_type is not None:
      logging.error('Exception occurred in Database context: *NOT* saving DB due to exception')
      return  # do not save if there was an exception
    self.Save()

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
      if self._safe_save and self._config.path.exists():
        logging.debug('Safe save enabled, reading existing DB before saving to prevent data loss')
        existing_db: _DBType = cast(
          '_DBType',
          self._config.DeSerialize(
            decryption_key=self._key, unpickler=key.UnpickleJSON, silent=True
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
      self._db.update({
        'db_version': self._db['db_version'] + 1,  # increment DB version on each save
        'app_version': __version__,  # set to current package version on creation
        'last_save': timer.Now(),
      })
      # save the DB to disk with optional encryption and compression
      self._config.Serialize(
        cast('tbase.JSONDict', self._db),
        encryption_key=self._key,
        pickler=key.PickleJSON,
        compress=_DB_COMPRESS_LEVEL if self._compress_save else None,
      )
      logging.info(f'DB saved to {self._config.path}: {prev_label} -> {self.label}')


def _DBLabel(db: _DBType) -> str:
  """Get a human-readable label for the database, for logging and display purposes.

  Returns:
    string '#<N>@<tm>'

  """
  return f'#{db["db_version"]}@{timer.TimeStr(db["last_save"])}'
