# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Pixel and disk operations for rendering.

For info on the PNG format and metadata handling, see:
https://pillow.readthedocs.io/en/stable/PIL.html#PIL.PngImagePlugin.PngInfo
"""

from __future__ import annotations

import base64
import dataclasses
import enum
import io
import json
import logging
import math
import pathlib
import subprocess  # noqa: S404
import sys
import tempfile
import time
from collections import abc
from typing import Any, cast

import gmpy2
import imageio
import imageio_ffmpeg  # type: ignore
import numpy as np
from numpy.typing import NDArray
from PIL import ExifTags, ImageDraw, ImageFont, PngImagePlugin
from PIL import Image as PILImage
from transcrypto.core import hashes
from transcrypto.utils import base as tbase
from transcrypto.utils import timer

from tranzoom import __app__ as _app
from tranzoom.core import frame, palette

# constants for drawing

_SQRT_TWO: float = math.sqrt(2)
_LINE_WIDTH_RATIO: int = 150  # line width will be max(1, sz//_LINE_WIDTH_RATIO) of the image width
_CIRCLE_RADIUS: int = 20
_LABEL_OFFSET: int = 5
# scale factor for converting stored Set interior integers back to |z| float magnitudes;
# interior points are stored as -(int(floor(scale * |z|)) + 1), with scale = RES / MAX_Z = RES / 2


class Error(frame.Error):
  """Base image exception."""


class Color(enum.Enum):
  """Color enum."""

  BLACK = (0, 0, 0)
  WHITE = (255, 255, 255)
  RED = (255, 0, 0)
  GREEN = (0, 255, 0)
  BLUE = (0, 0, 255)
  YELLOW = (255, 255, 0)
  CYAN = (0, 255, 255)
  MAGENTA = (255, 0, 255)


class ImageEncoding(enum.Enum):
  """Image file encoding type enum."""

  PNG = 'png'  # also the file suffix!
  GIF = 'gif'
  JPG = 'jpg'


class AnimationEncoding(enum.Enum):
  """Animation file encoding type enum."""

  GIF = 'gif'  # also the file suffix!
  MP4 = 'mp4'


class Resampling(enum.IntEnum):
  """Resampling filter enum."""

  # implemented in numpy locally
  BILINEAR = 100  # there is a PILImage.Resampling.BILINEAR, but we NEED THIS TO BE DIFFERENT
  # implemented in PIL
  BICUBIC = PILImage.Resampling.BICUBIC
  LANCZOS = PILImage.Resampling.LANCZOS


DEFAULT_RESAMPLING: Resampling = Resampling.BICUBIC


# GIF has is_animated, but we have to check for it
DetectAnimGIF: abc.Callable[[PILImage.Image], bool] = lambda img: (  # pyright: ignore[reportUnknownLambdaType]
  hasattr(img, 'is_animated') and img.is_animated  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
)
# MP4: has an 'ftyp' ISO base media box at bytes 4-8; PILImage.open() raises on MP4, so we
# must detect and handle it before reaching PIL
DetectMP4: abc.Callable[[bytes], bool] = lambda img_b: len(img_b) >= 8 and img_b[4:8] == b'ftyp'  # noqa: PLR2004


class OverlayType(enum.Enum):
  """Overlay type enum."""

  GRID = 'grid'
  CARDINAL = 'cardinal'


# basic computation constants

MAX_COLOR: int = 255  # max color value for 8-bit RGB channels
JPEG_QUALITY: int = 95  # quality for JPEG output; ignored for PNG which is lossless
MAX_INTERPOLATION_FRAMES: int = 7  # sanity limit for number of interpolated frames
DEFAULT_ANIMATION_TYPE: AnimationEncoding = AnimationEncoding.GIF

# hash key is the only meta key that has to be known here b/c we have to read it from files

META_IMAGE_HASH_KEY: str = f'{_app}:image:hash'  # str, like "abcdef1234567890", a SHA256

# color constants

DEFAULT_MARK_COLOR: Color = Color.RED
DEFAULT_MARK_WIDTH: int = 1
MIN_MARK_WIDTH: int = 1
MAX_MARK_WIDTH: int = 50

# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class RenderParameters(frame.SerializingFractalObject):
  """Defines a transformation from math to image of a single image.

  ATTENTION: changing any attribute changes the object SHA-256 hash.

  Attributes:
    tp (FileType): Output file type; default is FileType.PNG.
    escaped_pal (palette.Palette): Color palette for escaped (exterior) points;
        default is palette.DEFAULT_PALETTE.
    set_pal (palette.Palette | None): Color palette for interior Set points; None means no
        Set palette (requires a non-Set computation); default is None.
    i_pixels (int): Number of pixels to interpolate between each pixel; default is 0
    mark_re (gmpy2.mpq): Real part of the optional crosshair mark coordinate;
        default is 0; unused when mark_color is None.
    mark_im (gmpy2.mpq): Imaginary part of the optional crosshair mark coordinate;
        default is 0; unused when mark_color is None.
    mark_color (Color | None): Color of the crosshair mark overlay; None means no mark is
        drawn; default is None.
    mark_width (int): Crosshair mark line width in pixels; default is DEFAULT_MARK_WIDTH.
    overlay (OverlayType | None): Optional numbered sector grid overlay; None means no
        overlay; default is None.

  """

  # ATTENTION: changing anything here changes the HASH!!
  tp: ImageEncoding = ImageEncoding.PNG
  escaped_pal: palette.Palette = palette.DEFAULT_PALETTE
  set_pal: palette.Palette | None = None  # if None, this must be a non-Set-computation
  i_pixels: int = 0  # for interpolation, number of pixels to interpolate between each pixel
  mark_re: gmpy2.mpq = _MPQ_ZERO
  mark_im: gmpy2.mpq = _MPQ_ZERO
  mark_color: Color | None = None  # if None, no mark will be drawn
  mark_width: int = DEFAULT_MARK_WIDTH
  overlay: OverlayType | None = None  # overlay is independent of mark!

  def __post_init__(self) -> None:
    """Check parameters for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check type is valid
    if self.tp != ImageEncoding.PNG:
      raise Error(f'Unsupported file type for rendering: {self.tp}')
    # check overlay is valid: for now we only allow GRID overlay
    if self.overlay and self.overlay != OverlayType.GRID:
      raise Error(f'Unknown overlay: {self.overlay}')
    # check palettes are valid
    if self.escaped_pal not in palette.Palette:
      raise Error(f'Unknown escaped palette: {self.escaped_pal}')
    if self.set_pal is not None and self.set_pal not in palette.Palette:
      raise Error(f'Unknown set palette: {self.set_pal}')
    # check i_pixels is valid
    frame.ValidateIPixels(self.i_pixels)
    # check mark width is valid
    if not (MIN_MARK_WIDTH <= self.mark_width <= MAX_MARK_WIDTH):
      raise Error(
        f'Mark width must be between {MIN_MARK_WIDTH} and {MAX_MARK_WIDTH}, got {self.mark_width}'
      )
    # check mark color is valid
    if self.mark_color is None:
      # we do not allow mark_re/im to be non-zero if no mark to be added to image
      if self.mark_re != _MPQ_ZERO or self.mark_im != _MPQ_ZERO:
        raise Error(
          'Mark positions expected to be (0, 0) when no mark color is specified, '
          f'got ({self.mark_re}, {self.mark_im})'
        )
    else:
      if self.mark_color not in Color:
        raise Error(f'Unknown mark color: {self.mark_color}')
      r: int
      g: int
      b: int
      r, g, b = self.mark_color.value
      if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):  # noqa: PLR2004
        raise Error(f'Mark color RGB values must be between 0 and 255, got {self.mark_color}')

  def __str__(self) -> str:
    """Get string representation of the RenderParameters.

    Format is:
    - "{[<FILE_TYPE>*<PX+1>: <ESCAPED_PALETTE>, <SET_PALETTE>]<MARK_IF_ANY><OVERLAY_IF_ANY>}"
    - `<FILE_TYPE>` is the file type in uppercase, like "PNG".
    - `<PX+1>` is the number of i_pixels + 1
    - `<ESCAPED_PALETTE>` is the name of the palette used for escaped points, in
        lowercase, like "sunset".
    - `<SET_PALETTE>` is the name of the palette used for interior Set points, in lowercase,
        like "ocean", or "none" if not used.
    - `<MARK_IF_ANY>` is " + [MARK: <MARK_COLOR>/<MARK_WIDTH> @ (<MARK_RE>, <MARK_IM>)]" if a
        mark is specified, or "" if no mark is specified.
    - `<OVERLAY_IF_ANY>` is " + [OVERLAY: <OVERLAY_TYPE>]" if an overlay is specified,
        or "" if no overlay is specified.

    Returns:
      str: String representation of the RenderParameters.

    """
    mark: str = (
      ''
      if self.mark_color is None
      else (
        f' + [MARK: {self.mark_color.name.lower()}/{self.mark_width} '
        f'@ ({self.mark_re}, {self.mark_im})]'
      )
    )
    overlay: str = '' if self.overlay is None else f' + [OVERLAY: {self.overlay.name}]'
    return (
      '{'
      f'[{self.tp.name.upper()}*{self.i_pixels + 1}: {self.escaped_pal.name}, '
      f'{self.set_pal.name if self.set_pal else "none"}]{mark}{overlay}'
      '}'
    )

  @property
  def json(self) -> tbase.JSONDict:
    """JSON-serializable dictionary representation of the RenderParameters.

    Keys: `tp`, `escaped_pal`, `set_pal`, `mark_re`, `mark_im`, `mark_color`,
    `mark_width`, `overlay`.

    Returns:
      tbase.JSONDict: A dictionary representation of the RenderParameters.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'tp': self.tp.value,
      'escaped_pal': self.escaped_pal.value,
      'set_pal': self.set_pal.value if self.set_pal else None,
      'i_pixels': self.i_pixels,
      'mark_re': str(self.mark_re),
      'mark_im': str(self.mark_im),
      # BEWARE: we store the mark color as lowercase name, not the RGB value
      'mark_color': self.mark_color.name.lower() if self.mark_color else None,
      'mark_width': self.mark_width,
      'overlay': self.overlay.value if self.overlay else None,
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> RenderParameters:
    """Create a RenderParameters from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from RenderParameters.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the RenderParameters.
          If the calculated hash does not match, an error is raised.

    Returns:
      RenderParameters: A RenderParameters object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params = RenderParameters(  # object creation will check the data is valid and consistent
        tp=ImageEncoding(data.get('tp', ImageEncoding.PNG.value)),
        escaped_pal=palette.Palette(data.get('escaped_pal', palette.DEFAULT_PALETTE.value)),
        set_pal=palette.Palette(data['set_pal']) if data.get('set_pal') else None,
        i_pixels=int(str(data.get('i_pixels', '0'))),
        mark_re=gmpy2.mpq(str(data.get('mark_re', '0'))),
        mark_im=gmpy2.mpq(str(data.get('mark_im', '0'))),
        mark_color=(  # upper -> convert by name
          Color[str(data['mark_color']).upper()] if data.get('mark_color') else None
        ),
        mark_width=int(str(data.get('mark_width', DEFAULT_MARK_WIDTH))),
        overlay=OverlayType(data['overlay']) if data.get('overlay') else None,
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid RenderParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'RenderParameters {params.sha!r} does not match expected {check_hash!r}')
    return params


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class RenderAnimationParameters(RenderParameters):
  """Defines a transformation from math to image of an animation.

  ATTENTION: changing any attribute changes the object SHA-256 hash.

  Attributes:
    anim (AnimationEncoding): Output file type; default is AnimationEncoding.GIF.
    tp (FileType): Output type for animation frames; default is FileType.PNG.
    escaped_pal (palette.Palette): Color palette for escaped (exterior) points;
        default is palette.DEFAULT_PALETTE.
    set_pal (palette.Palette | None): Color palette for interior Set points; None means no
        Set palette (requires a non-Set computation); default is None.
    i_frames (int): Number of frames to interpolate between each frame; default is 0
    i_pixels (int): Number of pixels to interpolate between each pixel; default is 0
    mark_re (gmpy2.mpq): Real part of the optional crosshair mark coordinate;
        default is 0; unused when mark_color is None.
    mark_im (gmpy2.mpq): Imaginary part of the optional crosshair mark coordinate;
        default is 0; unused when mark_color is None.
    mark_color (Color | None): Color of the crosshair mark overlay; None means no mark is
        drawn; default is None.
    mark_width (int): Crosshair mark line width in pixels; default is DEFAULT_MARK_WIDTH.
    overlay (OverlayType | None): Optional numbered sector grid overlay; None means no
        overlay; default is None.

  """

  # ATTENTION: changing anything here changes the HASH!!
  anim: AnimationEncoding = AnimationEncoding.GIF
  i_frames: int = 0  # for interpolation, number of frames to interpolate between each frame

  def __post_init__(self) -> None:
    """Check parameters for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    super(RenderAnimationParameters, self).__post_init__()
    # check type is valid
    if self.anim not in {AnimationEncoding.GIF, AnimationEncoding.MP4}:
      raise Error(f'Unsupported animation type for rendering: {self.anim}')
    # check i_frames is valid
    ValidateIFrames(self.i_frames)

  def __str__(self) -> str:
    """Get string representation of the RenderAnimationParameters.

    Format is:
    - "<<ANIM_TYPE>*<FRM+1>: RENDER_PARAMS>"
    - `<ANIM_TYPE>` is the animation type in uppercase, like "MP4".
    - `<FRM+1>` is the number of i_frames + 1

    Returns:
      str: String representation of the RenderAnimationParameters.

    """
    return (
      f'<{self.anim.name.upper()}*{self.i_frames + 1}: '
      f'{super(RenderAnimationParameters, self).__str__()}>'
    )

  @property
  def json(self) -> tbase.JSONDict:
    """JSON-serializable dictionary representation of the RenderAnimationParameters.

    Keys: `anim`, `i_frames`, `render`.

    Returns:
      tbase.JSONDict: A dictionary representation of the RenderAnimationParameters.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'anim': self.anim.value,
      'i_frames': self.i_frames,
      'render': super(RenderAnimationParameters, self).json,
    }

  @staticmethod
  def FromRender(
    render: RenderParameters, *, anim: AnimationEncoding = AnimationEncoding.GIF, i_frames: int = 0
  ) -> RenderAnimationParameters:
    """Create a RenderAnimationParameters from its parent plus type and i_frames.

    Args:
      render (RenderParameters): The parent RenderParameters.
      anim (AnimationEncoding): The animation type, default is GIF.
      i_frames (int): The number of i_frames, default is 0.

    Returns:
      RenderAnimationParameters: A RenderAnimationParameters object

    """
    return RenderAnimationParameters(
      anim=anim,
      tp=render.tp,
      escaped_pal=render.escaped_pal,
      set_pal=render.set_pal,
      i_frames=i_frames,
      i_pixels=render.i_pixels,
      mark_re=render.mark_re,
      mark_im=render.mark_im,
      mark_color=render.mark_color,
      mark_width=render.mark_width,
      overlay=render.overlay,
    )

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> RenderAnimationParameters:
    """Create a RenderAnimationParameters from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from RenderAnimationParameters.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the
          RenderAnimationParameters. If the calculated hash does not match, an error is raised.

    Returns:
      RenderAnimationParameters: A RenderAnimationParameters object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params: RenderAnimationParameters = RenderAnimationParameters.FromRender(
        RenderParameters.FromJson(cast('tbase.JSONDict', data['render'])),
        anim=AnimationEncoding(data.get('anim', AnimationEncoding.GIF.value)),
        i_frames=int(str(data.get('i_frames', '0'))),
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid RenderAnimationParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(
        f'RenderAnimationParameters {params.sha!r} does not match expected {check_hash!r}'
      )
    return params


def MakeImagePath(
  img_output_path: pathlib.Path | None,
  img_use_date: bool,
  img_use_hash: bool,
  img_path_prefix: str,
  raw_hash: str,
  *,
  tm: int | None = None,
  add_serial: int | None = None,
  suffix: str = 'png',
) -> pathlib.Path:
  """Make a file path for saving the image, based on the configuration and image hash.

  Args:
    img_output_path (pathlib.Path | None): The output directory path. If None, the current
        directory is used.
    img_use_date (bool): Whether to include the current date in the file name.
    img_use_hash (bool): Whether to include the image hash in the file name.
    img_path_prefix (str): The prefix for the file name.
    raw_hash (str): The hash of the image data.
    tm (int | None): Optional timestamp to use for the date in the file name. If None, the
        current time is used.
    add_serial (int | None): Optional serial number to include in the file name for uniqueness;
        if None, no serial number is included; if provided, it is formatted as a zero-padded
        5-digit number between the date and hash.
    suffix (str): The file extension/suffix to use, default is "png".

  Returns:
    pathlib.Path: The full path for saving the image.

  Raises:
    Error: If the img_path_prefix is invalid (contains path separators).

  """
  # save the image to a file named by its time/hash
  tm_str: str = time.strftime('%Y%m%d%H%M%S', time.gmtime(tm or timer.Now()))
  # validate that img_path_prefix is a basename (no path separators) to prevent directory traversal
  filename: str = img_path_prefix
  if pathlib.Path(filename).name != img_path_prefix:
    raise Error(f'Invalid prefix: {img_path_prefix!r} has path separators (ex: "/" or "\\")')
  # add date and hash to the file name if requested
  if img_use_date:
    filename += f'-{tm_str}'
  if add_serial is not None:
    filename += f'-{add_serial:05}'  # add a serial number
  if img_use_hash:
    # use 20 chars of the hash to avoid very long file names; 20 chars = 10 bytes = 80 bits;
    # collision is 1 in 2**40 ~ 1 in 1 trillion, which is good enough for our use case
    filename += f'-{raw_hash[:20]}'
  # add .png extension, make full path, and save the file
  filename += '.' + suffix.strip().lower()
  return (
    (pathlib.Path(filename) if img_output_path is None else img_output_path / filename)
    .expanduser()
    .resolve()
  )


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ObjInfo(frame.SerializingFractalObject):
  """Represents information on an image or animation, but not the data.

  Attributes:
    img (ImageEncoding | None): Only present if this is an image; None if this is an animation.
    anim (AnimationEncoding | None): Only present if this is an animation; None if this is an image.
    width (int): Width of the image/animation in pixels.
    height (int): Height of the image/animation in pixels.
    bin_hash (str): SHA-256 hash of the binary data of the image or animation.
    data_hash (str): SHA-256 hash of the pixel data of the image or animation.
    meta (dict[str, str]): Metadata associated with the image or animation.

  """

  img: ImageEncoding | None = None
  anim: AnimationEncoding | None = None
  width: int
  height: int
  bin_hash: str
  data_hash: str
  meta: dict[str, str]

  def __post_init__(self) -> None:
    """Check ObjInfo for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check that either img or anim is set, but not both
    if (self.img is None and self.anim is None) or (self.img is not None and self.anim is not None):
      raise Error(f'Exactly one of img or anim must be set, got {self.img=} and {self.anim=}')
    # check width and height are valid
    if not (frame.MIN_IMAGE_SIZE <= self.width <= frame.MAX_IMAGE_SIZE) or not (
      frame.MIN_IMAGE_SIZE <= self.height <= frame.MAX_IMAGE_SIZE
    ):
      raise Error(
        f'{self.width=} and {self.height=} must be '
        f'between {frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
      )
    # check bin_hash and data_hash are valid hex strings of length 64 (SHA-256)
    for hash_name, hash_value in [('bin_hash', self.bin_hash), ('data_hash', self.data_hash)]:
      if len(hash_value) != 64 or not all(c in '0123456789abcdef' for c in hash_value.lower()):  # noqa: PLR2004
        raise Error(f'{hash_name} must be a 64-character hex string, got {hash_value=}')

  def __str__(self) -> str:
    """Get string representation of the ObjInfo.

    Format is:
    - ""

    Returns:
      str: String representation of the ObjInfo.

    """
    tp: str = ''
    if self.img is not None:
      tp = f'{self.img.name.upper()}.img'
    elif self.anim is not None:
      tp = f'{self.anim.name.upper()}.anim'
    return (
      f'[{tp}: {self.width} \u00d7 {self.height}, BIN:{self.bin_hash!r}, '
      f'DATA:{self.data_hash!r}, {self.meta}]'
    )

  @property
  def json(self) -> tbase.JSONDict:
    """JSON-serializable dictionary representation of the ObjInfo.

    Keys: `tp`, `escaped_pal`, `set_pal`, `mark_re`, `mark_im`, `mark_color`,
    `mark_width`, `overlay`.

    Returns:
      tbase.JSONDict: A dictionary representation of the ObjInfo.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'img': self.img.value if self.img else None,
      'anim': self.anim.value if self.anim else None,
      'width': self.width,
      'height': self.height,
      'bin_hash': self.bin_hash,
      'data_hash': self.data_hash,
      'meta': cast('tbase.JSONDict', self.meta),
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> ObjInfo:
    """Create a ObjInfo from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from ObjInfo.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the ObjInfo.
          If the calculated hash does not match, an error is raised.

    Returns:
      ObjInfo: An ObjInfo object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params: ObjInfo = ObjInfo(
        img=ImageEncoding(data['img']) if data.get('img') else None,
        anim=AnimationEncoding(data['anim']) if data.get('anim') else None,
        width=int(str(data['width'])),
        height=int(str(data['height'])),
        bin_hash=str(data['bin_hash']),
        data_hash=str(data['data_hash']),
        meta=cast('dict[str, str]', data['meta']),
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid ObjInfo JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'ObjInfo {params.sha!r} does not match expected {check_hash!r}')
    return params


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class Pixels(frame.SerializingFractalObject):
  """Represents pixel data for an image."""

  data: NDArray[np.float32]
  meta: dict[str, str]

  def __post_init__(self) -> None:
    """Check Pixels for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check data shape is valid
    width: int
    height: int
    channels: int
    height, width, channels = self.data.shape
    if channels != 3:  # noqa: PLR2004
      raise Error(f'Expected data shape (height, width, 3), got {self.data.shape}')
    # check width and height are valid
    if not (frame.MIN_IMAGE_SIZE <= width <= frame.MAX_IMAGE_SIZE) or not (
      frame.MIN_IMAGE_SIZE <= height <= frame.MAX_IMAGE_SIZE
    ):
      raise Error(
        f'{width=} and {height=} must be between {frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
      )

  def __str__(self) -> str:
    """Get string representation of the Pixels.

    Format is:
    - "[<WIDTH>, <HEIGHT>, <DATA_HASH>, <META>]"

    Returns:
      str: String representation of the Pixels.

    """
    return f'[{self.width}, {self.height}, {self.data_hash!r}, {self.meta}]'

  def PrintITerm2(self) -> None:
    """Print the image to `sys.stdout` in iTerm2, using the iTerm2 inline image protocol.

    <https://iterm2.com/documentation-images.html>

    """
    PrintITerm2(self.PNG(copy_previous=False)[0])

  @property
  def width(self) -> int:
    """Width of the pixel data.

    Returns:
      int: The width of the pixel data.

    """
    return cast('int', self.data.shape[1])

  @property
  def height(self) -> int:
    """Height of the pixel data.

    Returns:
      int: The height of the pixel data.

    """
    return cast('int', self.data.shape[0])

  @property
  def clip(self) -> NDArray[np.uint8]:
    """Clip the pixel data to the valid range [0, MAX_COLOR] and convert to uint8.

    Uses explicit rounding to ensure deterministic conversion from float32 to uint8,
    avoiding platform-dependent implicit rounding behavior.

    Returns:
      NDArray[np.uint8]: The clipped pixel data as a uint8 array.

    """
    return np.round(np.clip(self.data, 0, MAX_COLOR)).astype(np.uint8)

  @property
  def obj(self) -> PILImage.Image:
    """A PIL Image object from the pixel data.

    Returns:
      PILImage.Image: A PIL Image object representing the pixel data.

    """
    return PILImage.fromarray(self.clip, mode='RGB')

  @property
  def data_hash(self) -> str:
    """Hash of the pixel data.

    Returns:
      str: A hexadecimal string representing the hash of the pixel data.

    """
    return hashes.Hash256(self.clip.tobytes()).hex()

  def UpdateHash(self) -> str:
    """Update the image hash in the metadata to reflect the current pixel data.

    Returns:
      str: The updated hash of the pixel data.

    """
    hsh: str = self.data_hash
    if META_IMAGE_HASH_KEY in self.meta:
      # if we have a populated image hash, update it to reflect the resized pixel data
      self.meta[META_IMAGE_HASH_KEY] = hsh
    return hsh

  @property
  def json(self) -> tbase.JSONDict:
    """JSON-serializable dictionary representation of the Pixels.

    Keys: `width`, `height`, `data_hash`, `meta`.

    Returns:
      tbase.JSONDict: A dictionary representation of the Pixels.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'data': self.data.tobytes().hex(),
      'meta': cast('tbase.JSONDict', self.meta),
      'width': self.width,  # store width so we can recover the shape
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> Pixels:
    """Create a Pixels from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from Pixels.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the Pixels.
          If the calculated hash does not match, an error is raised.

    Returns:
      Pixels: A Pixels object

    Raises:
      Error: on error

    """
    # create the object
    try:
      dt: NDArray[np.float32] = np.frombuffer(bytes.fromhex(str(data['data'])), dtype=np.float32)
      width: int = int(str(data['width']))
      if len(dt.shape) != 1 or dt.shape[0] % (width * 3):
        raise Error(f'Pixels length {dt.shape[0]} is not a multiple of {width=} * 3 channels')  # noqa: TRY301
      params: Pixels = Pixels(
        data=dt.reshape(dt.shape[0] // (width * 3), width, 3),
        meta=cast('dict[str, str]', data['meta']),
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid Pixels JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'Pixels {params.sha!r} does not match expected {check_hash!r}')
    return params

  @staticmethod
  def FromPIL(  # noqa: C901, PLR0912
    img: PILImage.Image, *, allow_conversion: bool = False
  ) -> tuple[Pixels, ImageEncoding, str]:
    """Create a Pixels object from a PIL Image object.

    Args:
      img (PILImage.Image): The image data as a PIL Image object
      allow_conversion (bool): If False (default) will only accept PNG RGB images; if True
          will try to open any non-animation image and convert data from other modes to RGB

    Returns:
      tuple[Pixels, ImageEncoding, str]: A Pixels object containing the image data and metadata,
          the image format, and the SHA-256 hash of the internal bytes image data.


    Raises:
      Error: on error

    """
    # check for animated images, which are not supported
    if DetectAnimGIF(img):
      raise Error('Animated GIF images are not supported for Pixels')
    # check source type
    try:
      img_format: ImageEncoding | None = ImageEncoding((img.format).lower()) if img.format else None
    except (ValueError, KeyError) as err:
      raise Error(f'Unsupported image format: {img.format!r}') from err
    if img_format and img_format != ImageEncoding.PNG and not allow_conversion:
      raise Error(f'Expected PNG format, got {img_format!r}')
    # get metadata, but different formats may encode metadata differently!
    meta: dict[str, str] = {}
    if img_format is None or img_format == ImageEncoding.PNG:
      # PNG metadata is stored in img.info as a dict of str -> str
      meta = _LoadAndCheckMetadataKeys(img.info.items())
    elif img_format == ImageEncoding.JPG:
      # JPG metadata is stored in EXIF tags, which are numeric keys; we convert to str
      exif: PILImage.Exif | None = img.getexif()
      if exif:
        try:
          meta = _LoadAndCheckMetadataKeys(
            json.loads(str(exif[ExifTags.Base.ImageDescription])).items()
          )
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError, KeyError) as err:
          logging.error(f'JPG exif {ExifTags.Base.ImageDescription} is not valid, ignoring: {err}')
    elif img_format == ImageEncoding.GIF:
      # for GIFs we expect the metadata to be stored in the "comment" field as a JSON string
      try:
        meta = _LoadAndCheckMetadataKeys(
          json.loads(cast('bytes', img.info['comment']).decode('utf-8')).items()
        )
      except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError, KeyError) as err:
        logging.error(f'GIF "comment" metadata is not valid, ignoring: {err}')
    else:
      raise Error(f'Unsupported image format: {img_format!r}')
    # check mode, convert if needed/allowed
    rgb_img: PILImage.Image
    if img.mode == 'RGB':
      rgb_img = img
    else:
      if not allow_conversion:
        raise Error(f'Unsupported image mode {img.mode!r}, expected RGB')
      rgb_img = img.convert('RGB')
    # create object
    return (
      Pixels(
        data=np.asarray(rgb_img, dtype=np.float32),  # __post_init__ will check width/height/shape
        meta=meta,
      ),
      img_format or ImageEncoding.PNG,  # default to PNG if unknown
      hashes.Hash256(rgb_img.tobytes()).hex(),
    )

  @staticmethod
  def FromBytes(img_data: bytes, *, allow_conversion: bool = False) -> tuple[Pixels, ObjInfo]:
    """Create a Pixels object from image bytes (PNG, GIF, or MP4).

    Args:
      img_data (bytes): The image data as bytes; cannot be empty; must represent a non-animated
          PNG, GIF, BMP or JPG as bytes on disk
      allow_conversion (bool): If False (default) will only accept PNG RGB images; if True
          will try to open any non-animation image and convert data from other modes to RGB

    Returns:
      tuple[Pixels, ObjInfo]: A Pixels object containing the image data and metadata and
          the ObjInfo object containing the image type, dimensions, and hashes.

    Raises:
      Error: on error

    """
    # check for no data, hash the whole thing
    if not img_data:
      raise Error('No image data provided')
    if DetectMP4(img_data):
      raise Error('MP4 animation data is not supported for Pixels')
    bin_hash: str = hashes.Hash256(img_data).hex()
    # open as image, with PIL
    with PILImage.open(io.BytesIO(img_data)) as img:
      pix: Pixels
      tp: ImageEncoding
      hsh: str
      pix, tp, hsh = Pixels.FromPIL(img, allow_conversion=allow_conversion)
      return (
        pix,
        ObjInfo(
          img=tp,
          width=pix.width,
          height=pix.height,
          bin_hash=bin_hash,
          data_hash=hsh,
          meta=pix.meta.copy(),
        ),
      )

  def PNG(
    self, *, meta: dict[str, str] | None = None, copy_previous: bool = True
  ) -> tuple[bytes, str, str]:
    """Encode as PNG bytes.

    Args:
      meta (dict[str, str] | None): Optional additional metadata to include in the image;
          default is None.
      copy_previous (bool): Whether to copy existing metadata from `self.meta` into the image;
          default is True.

    Returns:
      tuple[bytes, str, str]: The PNG-encoded bytes of the image, its file hash, and its pixel hash.

    """
    # embed frame parameters as PNG tEXt metadata chunks; keys use a "tranZoom:" (_app) namespace
    png_meta: PngImagePlugin.PngInfo | None = None
    if meta or (copy_previous and self.meta):
      png_meta = PngImagePlugin.PngInfo()
      # copy any existing metadata from the original image
      if copy_previous and self.meta:
        for k, v in self.meta.items():
          png_meta.add_text(k, v)
      # add any extra metadata passed in
      if meta:
        for k, v in meta.items():
          png_meta.add_text(k, v)
    # save to PNG bytes
    with io.BytesIO() as buf, self.obj as img:
      img.save(buf, format='PNG', pnginfo=png_meta)
      img_data: bytes = buf.getvalue()
      return (img_data, hashes.Hash256(img_data).hex(), hashes.Hash256(img.tobytes()).hex())

  def JPG(
    self, *, meta: dict[str, str] | None = None, copy_previous: bool = True
  ) -> tuple[bytes, str, str]:
    """Encode as JPG bytes.

    Args:
      meta (dict[str, str] | None): Optional additional metadata to include in the image;
          default is None.
      copy_previous (bool): Whether to copy existing metadata from `self.meta` into the image;
          default is True.

    Returns:
      tuple[bytes, str, str]: The JPG-encoded bytes of the image, its file hash, and its pixel hash.

    """
    # store metadata as compact JSON in EXIF ImageDescription (tag 0x010E)
    exif: PILImage.Exif | None = None
    if meta or (copy_previous and self.meta):
      # copy any existing metadata from the original image
      all_meta: dict[str, str] = self.meta.copy() if (copy_previous and self.meta) else {}
      # add any extra metadata passed in
      if meta:
        all_meta.update(meta)
      # store metadata as compact JSON in EXIF ImageDescription (tag 0x010E)
      exif = PILImage.Exif()
      exif[ExifTags.Base.ImageDescription] = json.dumps(all_meta, separators=(',', ':'))
    # save to PNG bytes
    with io.BytesIO() as buf, self.obj as img:
      img.save(
        buf,
        format='JPEG',
        quality=JPEG_QUALITY,
        optimize=True,
        exif=exif.tobytes() if exif else None,
      )
      img_data: bytes = buf.getvalue()
      return (img_data, hashes.Hash256(img_data).hex(), hashes.Hash256(img.tobytes()).hex())

  def Resize(
    self,
    width: int,
    height: int,
    *,
    resample: Resampling = DEFAULT_RESAMPLING,
  ) -> Pixels:
    """Resize Pixels to the specified dimensions by resampling. Keep metadata intact.

    Optionally, uses a deterministic numpy-based bilinear interpolation (Resampling.BILINEAR).

    Args:
      width (int): The target width in pixels.
      height (int): The target height in pixels.
      resample (Resampling): The resampling filter to use for resizing; Resampling.BILINEAR is a
          local implementation; other options use PIL's built-in resampling methods; the
          default is DEFAULT_RESAMPLING

    Returns:
      Pixels: The resized image data as a Pixels object.

    Raises:
      Error: on error

    """
    resized: NDArray[np.float32]
    # choose sampling method to generate the new pixels
    if resample in {Resampling.LANCZOS, Resampling.BICUBIC}:
      # for these resampling methods, we can use PIL directly
      with self.obj as img:
        resized = np.asarray(img.resize((width, height), resample=resample), dtype=np.float32)
    elif resample == Resampling.BILINEAR:
      # we manually implement bilinear interpolation with this option
      old_h: int
      old_w: int
      old_h, old_w = self.data.shape[0], self.data.shape[1]
      # calculate scaling factors
      scale_x: float = (old_w - 1) / (width - 1) if width > 1 else 0.0
      scale_y: float = (old_h - 1) / (height - 1) if height > 1 else 0.0
      # create output array
      resized = np.zeros((height, width, 3), dtype=np.float32)
      # for each output pixel, compute the corresponding source coordinates and interpolate
      for y in range(height):
        for x in range(width):
          # source coordinates in the original image
          src_x: float = x * scale_x
          src_y: float = y * scale_y
          # bilinear interpolation
          resized[y, x, 0], resized[y, x, 1], resized[y, x, 2] = _BilinearInterpolate(
            self.data, src_x, src_y, old_w, old_h
          )
    else:
      raise Error(f'Unsupported resampling method: {resample}')
    # copy metadata and update the image hash to reflect the resized pixel data
    pix: Pixels = Pixels(data=resized, meta=self.meta.copy())
    pix.UpdateHash()
    return pix

  def DrawCardinalInfoOverlay(self) -> Pixels:
    """Draw an overlay on the (512x512) image with target info for moving the zoom frame.

    Because of the text-on-image this is more efficient converting np.array -> PIL -> np.array.

    Overlays is:
    - white lines delimiting the quadrants of the image, intersecting at the center
    - 8 green circles around the center, indicating the 8 cardinal and ordinal directions
      to move the frame
    - each circle has a green label with its direction: "N", "NE", "E", "SE", "S", "SW", "W", "NW"

    Works on any size image, but is designed for 512x512, especially because of:
    - circle radius is fixed
    - text labels are fixed size and positioned with a fixed offset from the circle's center
    Fix these and it can work well on other sizes too...

    Returns:
      Pixels: The modified Pixels image data with the overlay drawn.

    """
    w: int
    h: int
    cx: int
    cy: int
    x: int
    y: int
    lw: int
    # open the image
    with self.obj as img:
      # draw the quadrant lines
      draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
      w, h = img.size
      cx, cy = w // 2, h // 2
      step_sz: int = w // frame.DEFAULT_STEP_DIRECT
      lw = max(1, max(w, h) // _LINE_WIDTH_RATIO)
      draw.line((0, cy, w, cy), fill=Color.WHITE.value, width=lw)
      draw.line((cx, 0, cx, h), fill=Color.WHITE.value, width=lw)
      # draw 8 circles around the center to indicate the 8 cardinal/ordinal directions
      font: ImageFont.ImageFont = cast('ImageFont.ImageFont', ImageFont.load_default())
      for dx, dy, direction in [
        (0, -step_sz, 'N'),
        (step_sz / _SQRT_TWO, -step_sz / _SQRT_TWO, 'NE'),
        (step_sz, 0, 'E'),
        (step_sz / _SQRT_TWO, step_sz / _SQRT_TWO, 'SE'),
        (0, step_sz, 'S'),
        (-step_sz / _SQRT_TWO, step_sz / _SQRT_TWO, 'SW'),
        (-step_sz, 0, 'W'),
        (-step_sz / _SQRT_TWO, -step_sz / _SQRT_TWO, 'NW'),
      ]:
        x, y = int(cx + dx), int(cy + dy)
        draw.ellipse(
          (x - _CIRCLE_RADIUS, y - _CIRCLE_RADIUS, x + _CIRCLE_RADIUS, y + _CIRCLE_RADIUS),
          outline=Color.GREEN.value,
          width=lw,
        )
        # for each circle, also draw the label text
        draw.text(
          (x - _LABEL_OFFSET, y - _LABEL_OFFSET), direction, fill=Color.GREEN.value, font=font
        )
      # done, save remembering to add metadata that this image has an overlay
      pix: Pixels = dataclasses.replace(Pixels.FromPIL(img)[0], meta=self.meta.copy())
      pix.UpdateHash()
      return pix

  def DrawThirdsInfoOverlay(self) -> Pixels:
    """Draw an overlay on an image of any size, with target info for moving the zoom frame.

    Because of the text-on-image this is more efficient converting np.array -> PIL -> np.array.

    Overlays:
    - white lines delimiting the 9 sections of the image
    - large green number labels (1-9) centered in each section, left-to-right, top-to-bottom

    Returns:
      Pixels: The modified Pixels image data with the overlay drawn.

    """
    w: int
    h: int
    cx: int
    cy: int
    col: int
    row: int
    lw: int
    # open the image
    with self.obj as img:
      # draw the thirds lines
      draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
      w, h = img.size
      cx, cy = w // 3, h // 3
      lw = max(1, max(w, h) // _LINE_WIDTH_RATIO)
      draw.line((0, cy, w, cy), fill=Color.WHITE.value, width=lw)
      draw.line((0, 2 * cy, w, 2 * cy), fill=Color.WHITE.value, width=lw)
      draw.line((cx, 0, cx, h), fill=Color.WHITE.value, width=lw)
      draw.line((2 * cx, 0, 2 * cx, h), fill=Color.WHITE.value, width=lw)
      # draw large number labels centered in each of the 9 sections, left-to-right, top-to-bottom
      label_font: ImageFont.FreeTypeFont = cast(
        'ImageFont.FreeTypeFont', ImageFont.load_default(size=int(max(cx, cy) / 3))
      )
      for row in range(3):
        for col in range(3):
          draw.text(
            (col * cx + cx // 2, row * cy + cy // 2),  # center of this section
            str(row * 3 + col + 1),  # label
            fill=Color.GREEN.value,
            font=label_font,
            anchor='mm',  # center it exactly
          )
      # done, save remembering to add metadata that this image has an overlay
      pix: Pixels = dataclasses.replace(Pixels.FromPIL(img)[0], meta=self.meta.copy())
      pix.UpdateHash()
      return pix

  def DrawCrossOverlay(
    self,
    x: int,
    y: int,
    *,
    col: Color = DEFAULT_MARK_COLOR,
    lw: int = DEFAULT_MARK_WIDTH,
  ) -> Pixels:
    """Draw a cross overlay on an image at the specified coordinates.

    Overlays:
    - a horizontal line spanning the image at the given y-coordinate
    - a vertical line spanning the image at the given x-coordinate

    Args:
      x (int): The x-coordinate of the center of the cross.
      y (int): The y-coordinate of the center of the cross.
      col (Color): The color of the cross; default is DEFAULT_MARK_COLOR.
      lw (int): The line width of the cross in pixels; default is DEFAULT_MARK_WIDTH.

    Returns:
      Pixels: The modified Pixels image data with the overlay drawn.

    Raises:
      Error: If the coordinates are out of bounds or if there are issues processing the image.

    """
    # check inputs
    w: int
    h: int
    h, w, _ = self.data.shape
    if not (0 <= x < w) or not (0 <= y < h):
      raise Error(f'Invalid coordinates for cross overlay: {x=}, {y=}, image size {w=} x {h=}')
    if lw <= 0:
      raise Error(f'Invalid line width: {lw}')
    # draw the cross on a copy of the data array
    out: NDArray[np.float32] = self.data.copy()
    color: NDArray[np.float32] = np.asarray(col.value, dtype=np.float32)
    half_lw: int = lw // 2
    y0: int = max(0, y - half_lw)
    y1: int = min(h, y + half_lw + 1)
    x0: int = max(0, x - half_lw)
    x1: int = min(w, x + half_lw + 1)
    out[y0:y1, :, :] = color
    out[:, x0:x1, :] = color
    pix: Pixels = Pixels(data=out, meta=self.meta.copy())
    pix.UpdateHash()
    return pix


def GetBasicDataFromMP4(img_bytes: bytes) -> ObjInfo:
  """Retrieve basic data from an MP4.

  Args:
    img_bytes (bytes): The image data as bytes (PNG, GIF, or MP4).

  Returns:
    ObjInfo: Basic information about the MP4

  Raises:
    Error: on error

  """
  # MP4: has an 'ftyp' ISO base media box at bytes 4-8; PILImage.open() raises on MP4: check
  if not DetectMP4(img_bytes):
    raise Error('Not a valid MP4 file (missing ftyp box)')
  bin_hash: str = hashes.Hash256(img_bytes).hex()
  # we have to write the bytes to a temporary file because imageio_ffmpeg requires a file path
  width: int
  height: int
  with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
    tmp.write(img_bytes)
    tmp.flush()
    tmp_path = pathlib.Path(tmp.name)
    # get width/height via imageio (reliable); get_meta_data() does NOT expose container tags
    reader = imageio.get_reader(  # pyright: ignore[reportUnknownMemberType]
      tmp_path,
      format='ffmpeg',  # type: ignore[arg-type]
    )
    width, height = cast('tuple[int, int]', reader.get_meta_data().get('size', (0, 0)))  # type: ignore[union-attr]
    reader.close()
    # read container tags (including our JSON comment) via ffmpeg -f ffmetadata;
    # this is the only way to access format.tags since imageio doesn't expose them
    proc = subprocess.run(  # noqa: S603
      [
        imageio_ffmpeg.get_ffmpeg_exe(),
        '-v',
        'quiet',
        '-i',
        str(tmp_path),
        '-f',
        'ffmetadata',
        'pipe:1',
      ],
      capture_output=True,
      text=True,
      check=False,
    )
    if proc.returncode != 0:
      raise Error(f'ffmpeg failed reading MP4 metadata: {proc.stderr.strip()!r}')
    # parse ffmetadata format: key=value lines; comments start with ';', sections with '['
    mp4_tags: dict[str, str] = {}
    tag_k: str
    tag_v: str
    for line in proc.stdout.splitlines():
      if line.startswith((';', '[')) or '=' not in line:
        continue
      tag_k, tag_v = line.split('=', 1)
      mp4_tags[tag_k] = tag_v
    # metadata was stored by WriteVideoMP4 as a single JSON string in the 'comment' field
    # (mirrors how GIF stores metadata in its comment field)
    mp4_meta: tbase.JSONDict = {}
    data_hash: str = bin_hash
    # try to get the data hash from the JSON metadata; if not valid JSON, log an error and ignore it
    try:
      mp4_meta = json.loads(mp4_tags['comment'])
      data_hash = str(mp4_meta[META_IMAGE_HASH_KEY])
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError, KeyError):
      logging.error('MP4 comment metadata not valid JSON, ignoring; DO NOT trust this MP4 hash')
    # build the ObjInfo object
    return ObjInfo(
      anim=AnimationEncoding.MP4,
      width=width,
      height=height,
      bin_hash=bin_hash,
      data_hash=data_hash,
      meta=cast('dict[str, str]', mp4_meta),
    )


def GetBasicData(img_bytes: bytes) -> tuple[ObjInfo, Pixels | None]:
  """Retrieve basic data from an image or animation (PNG, GIF, or MP4) or load, if possible.

  Args:
    img_bytes (bytes): The image data as bytes (PNG, GIF, or MP4).

  Returns:
    tuple[ObjInfo, Pixels | None]: A tuple containing:
      - ObjInfo: Basic information about the image or animation.
      - Pixels | None: The loaded image as a Pixels object, or None if not applicable.

  Raises:
    Error: on error

  """
  if not img_bytes:
    raise Error('No image data provided')
  # we must detect and handle MP4 it before reaching PIL!
  if DetectMP4(img_bytes):
    return (GetBasicDataFromMP4(img_bytes), None)
  # non-MP4: try to load as an image and extract metadata
  try:
    pix: Pixels
    info: ObjInfo
    pix, info = Pixels.FromBytes(img_bytes, allow_conversion=True)
    return (info, pix)
  except Error as err:
    logging.info(err)
  # Pixels failed: the only reason we'll accept for now, is that the image is an animated GIF
  # open as image, with PIL
  with PILImage.open(io.BytesIO(img_bytes)) as img:
    # check source type; make absolutely sure it is an animated GIF
    try:
      img_format: AnimationEncoding = AnimationEncoding((img.format or '').lower())
    except Exception as err:
      raise Error(f'Unsupported image format: {img.format!r}') from err
    if img_format != AnimationEncoding.GIF or not DetectAnimGIF(img):
      raise Error(f'Expected animated GIF format, got {img_format!r} / anim. {DetectAnimGIF(img)}')
    # for GIFs we expect the metadata to be stored in the "comment" field as a JSON string
    meta: dict[str, str] = {}
    try:
      meta = _LoadAndCheckMetadataKeys(
        json.loads(cast('bytes', img.info['comment']).decode('utf-8')).items()
      )
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError, KeyError) as err:
      logging.error(f'GIF "comment" metadata is not valid, ignoring: {err}')
    data_hash: str
    if META_IMAGE_HASH_KEY in meta:
      # this is the happy path: the GIF has a valid hash in its metadata, so we can trust it
      data_hash = meta[META_IMAGE_HASH_KEY]
    else:
      data_hash = hashes.Hash256(img.convert('RGB').tobytes()).hex()
      logging.error(f'GIF does not have a tranZoom image hash; DO NOT TRUST this hash: {data_hash}')
    return (
      ObjInfo(
        anim=img_format,
        width=img.width,
        height=img.height,
        bin_hash=hashes.Hash256(img_bytes).hex(),
        data_hash=data_hash,
        meta=meta,
      ),
      None,
    )


def PrintITerm2(img_data: bytes) -> None:
  """Print the image to `sys.stdout` in iTerm2, using the iTerm2 inline image protocol.

  <https://iterm2.com/documentation-images.html>

  Args:
    img_data (bytes): The original PNG image data as bytes.

  """
  sys.stdout.write(
    f'\x1b]1337;File=inline=1;size={len(img_data)}:{base64.b64encode(img_data).decode("ascii")}\a\n'
  )
  sys.stdout.flush()


def ValidateIFrames(i_frames: int) -> None:
  """Validate the interpolation frames parameter.

  Args:
    i_frames (int): The number of interpolation frames to validate.

  Raises:
    Error: If i_frames is not between 0 and MAX_INTERPOLATION_FRAMES (inclusive).

  """
  if not (0 <= i_frames <= MAX_INTERPOLATION_FRAMES):
    raise Error(f'Interpolation must be between 0 and {MAX_INTERPOLATION_FRAMES}, got {i_frames=}')


def _BilinearInterpolate(
  data: NDArray[np.float32],
  src_x: float,
  src_y: float,
  old_w: int,
  old_h: int,
) -> tuple[float, float, float]:
  """Perform bilinear interpolation at the given source coordinates.

  Args:
    data (NDArray[np.float32]): The source image data array.
    src_x (float): Source x coordinate (float).
    src_y (float): Source y coordinate (float).
    old_w (int): Width of source image.
    old_h (int): Height of source image.

  Returns:
    tuple[float, float, float]: Interpolated RGB values.

  """
  # get the four surrounding pixels
  x0: int
  y0: int
  x0, y0 = int(np.floor(src_x)), int(np.floor(src_y))
  x1: int = min(x0 + 1, old_w - 1)
  y1: int = min(y0 + 1, old_h - 1)
  # get fractional parts for interpolation
  fx: float = src_x - x0
  fy: float = src_y - y0
  # bilinear interpolation for each channel
  return tuple(
    (
      (data[y0, x0, c] * (1.0 - fx) + data[y0, x1, c] * fx) * (1.0 - fy)
      + (data[y1, x0, c] * (1.0 - fx) + data[y1, x1, c] * fx) * fy
    )
    for c in range(3)
  )


def _LoadAndCheckMetadataKeys(img_m: abc.Iterable[tuple[Any, Any]]) -> dict[str, str]:
  """Load metadata keys from an iterable of key-value pairs. Checks that all keys are strings.

  Args:
    img_m (abc.Iterable[tuple[Any, Any]]): An iterable of key-value pairs representing metadata.

  Returns:
    dict[str, str]: A dictionary with string keys and string values representing the metadata.

  Raises:
    Error: If any key in the metadata is not a string.

  """
  m: dict[str, str] = {}
  for k, v in img_m:
    if not isinstance(k, str):
      raise Error(f'Invalid metadata key type {type(k)} for key {k!r}')
    m[k] = str(v)
  return m
