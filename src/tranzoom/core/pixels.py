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
from typing import cast

import gmpy2
import imageio
import imageio_ffmpeg  # type: ignore
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


class FileType(enum.Enum):
  """File type enum."""

  PNG = 'png'  # also the file suffix!
  GIF = 'gif'
  MP4 = 'mp4'


class OverlayType(enum.Enum):
  """Overlay type enum."""

  GRID = 'grid'
  CARDINAL = 'cardinal'


JPEG_QUALITY: int = 95  # quality for JPEG output; ignored for PNG which is lossless

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
  """Defines a transformation from math to image.

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
  tp: FileType = FileType.PNG
  escaped_pal: palette.Palette = palette.DEFAULT_PALETTE
  set_pal: palette.Palette | None = None  # if None, this must be a non-Set-computation
  i_pixels: int = 0  # for interpolation, number of pixels to interpolate between each pixel
  mark_re: gmpy2.mpq = _MPQ_ZERO
  mark_im: gmpy2.mpq = _MPQ_ZERO
  mark_color: Color | None = None  # if None, no mark will be drawn
  mark_width: int = DEFAULT_MARK_WIDTH
  overlay: OverlayType | None = None  # overlay is independent of mark!
  prev_marker: frame.Frame | None = None  # for zoom
  next_marker: frame.Frame | None = None  # for zoom

  def __post_init__(self) -> None:  # noqa: C901, PLR0912
    """Check parameters for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check type is valid
    if self.tp not in {FileType.PNG, FileType.GIF, FileType.MP4}:
      raise Error(f'Unknown file type: {self.tp}')
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
    # check prev/next markers are valid if provided
    if not self.prev_marker and self.next_marker:
      raise Error('next_marker provided without prev_marker')
    if self.prev_marker and not self.next_marker:
      raise Error('prev_marker provided without next_marker')
    if (
      self.prev_marker
      and self.next_marker
      and (self.prev_marker.fractal != self.next_marker.fractal)
    ):
      raise Error('prev/next_marker fractal types do not match')

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
    markers: str = (
      ''
      if self.prev_marker is None or self.next_marker is None
      else f' + [P:{self.prev_marker.sha[:10]}, N:{self.next_marker.sha[:10]}]'
    )
    return (
      '{'
      f'[{self.tp.name.upper()}*{self.i_pixels + 1}: {self.escaped_pal.name}, '
      f'{self.set_pal.name if self.set_pal else "none"}]{mark}{overlay}{markers}'
      '}'
    )

  @property
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the RenderParameters.

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
      'prev_marker': self.prev_marker.json if self.prev_marker else None,
      'next_marker': self.next_marker.json if self.next_marker else None,
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
        tp=FileType(data.get('tp', FileType.PNG.value)),
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
        prev_marker=frame.Frame.FromJson(cast('tbase.JSONDict', data['prev_marker']))
        if data.get('prev_marker')
        else None,
        next_marker=frame.Frame.FromJson(cast('tbase.JSONDict', data['next_marker']))
        if data.get('next_marker')
        else None,
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid RenderParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'RenderParameters {params.sha!r} does not match expected {check_hash!r}')
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


def GetBasicDataFromImage(img_bytes: bytes) -> tuple[int, int, str, tbase.JSONDict]:  # noqa: C901, PLR0912, PLR0915
  """Get basic data from an image (PNG, GIF, or MP4), including format, size, hash, and metadata.

  Args:
    img_bytes (bytes): The image data as bytes (PNG, GIF, or MP4).

  Returns:
    tuple[int, int, str, tbase.JSONDict]: (width, height, hash, metadata) where:
      - width: The width of the image in pixels.
      - height: The height of the image in pixels.
      - hash: A hash of the image data (SHA256 of RGB bytes).
      - metadata: The extracted metadata from the image.

  Raises:
    Error: If the image format is unsupported or if there are issues processing the image.

  """
  # MP4: has an 'ftyp' ISO base media box at bytes 4-8; PILImage.open() raises on MP4, so we
  # must detect and handle it before reaching PIL
  raw_hash: str
  width: int
  height: int
  if len(img_bytes) >= 8 and img_bytes[4:8] == b'ftyp':  # noqa: PLR2004
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
    if width < 1 or height < 1:
      raise Error(f'Invalid MP4 frame size {width} x {height}')
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
    raw_hash = ''
    if 'comment' in mp4_tags:
      try:
        mp4_meta = json.loads(mp4_tags['comment'])
        if META_IMAGE_HASH_KEY in mp4_meta:
          raw_hash = str(mp4_meta[META_IMAGE_HASH_KEY])
        else:
          logging.error('DO NOT trust this MP4 hash')
      except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        logging.error('MP4 comment metadata not valid JSON, ignoring; DO NOT trust this MP4 hash')
    if not raw_hash:
      logging.error(
        'MP4 missing %r in metadata; falling back to file hash (DO NOT trust)', META_IMAGE_HASH_KEY
      )
      raw_hash = hashes.Hash256(img_bytes).hex()
    return (width, height, raw_hash, mp4_meta)
  # PNG or GIF: use PIL to open and extract metadata
  with PILImage.open(io.BytesIO(img_bytes)) as img:
    # get the internal data we need (size and hash)
    width = img.width
    height = img.height
    if width < 1 or height < 1:
      raise Error(f'Invalid image size {width} x {height}')
    raw_hash = hashes.Hash256(img.convert('RGB').tobytes()).hex()  # not 'RGBA'!!
    # extract metadata from PNG
    img_metadata: tbase.JSONDict = img.info  # type: ignore[assignment]
    # make sure format is known and do any format-specific operations
    if (img_format := (img.format or '').upper()) == FileType.PNG.value.upper():
      pass  # nothing else to do for PNG, the metadata is already extracted in pil_info
    elif img_format == FileType.GIF.value.upper():
      # for GIFs we expect the metadata to be stored in the "comment" field as a JSON string
      if 'comment' in img_metadata:
        try:
          img_metadata = json.loads(cast('bytes', img_metadata['comment']).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
          # if comment is not valid JSON, just keep the original pil_info
          logging.error(
            'GIF image has comment metadata but it is not valid JSON, ignoring it; '
            'DO NOT trust this GIF hash'
          )
    elif img_format == FileType.MP4.value.upper():
      raise Error('MP4 format reached PIL unexpectedly; file bytes may not be a valid MP4')
    else:
      raise Error(f'Unsupported image format {img.format!r}, expected PNG')
    # if we managed to extract the metadata, then maybe we can also get the correct hash
    if META_IMAGE_HASH_KEY in img_metadata:
      raw_hash = str(img_metadata[META_IMAGE_HASH_KEY])
    else:
      logging.error('DO NOT trust this image hash')
  return (width, height, raw_hash, img_metadata)


def ResizePNG(
  img_data: bytes,
  width: int,
  height: int,
  *,
  resample: PILImage.Resampling = PILImage.Resampling.BICUBIC,
) -> bytes:
  """Resize PNG bytes and return PNG bytes without metadata.

  Args:
    img_data (bytes): The PNG image data as bytes.
    width (int): The target width in pixels.
    height (int): The target height in pixels.
    resample (PILImage.Resampling): The resampling filter to use for resizing; default is BICUBIC.

  Returns:
    bytes: The resized PNG image data as bytes.

  """
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
    # trivial case: if the image is already the requested size, just return the original bytes
    if img.size == (width, height):
      return img_data
    # resize the image and save to PNG bytes
    return PNGFromRGBImage(
      img.resize((width, height), resample=resample), meta=cast('dict[str, str]', img.info)
    )


def DrawCardinalInfoOverlay(img_data: bytes) -> bytes:
  """Draw an overlay on the (512x512) image with target info for moving the zoom frame.

  Overlays is:
  - white lines delimiting the quadrants of the image, intersecting at the center
  - 8 green circles around the center, indicating the 8 cardinal and ordinal directions
    to move the frame
  - each circle has a green label with its direction: "N", "NE", "E", "SE", "S", "SW", "W", "NW"

  Works on any size image, but is designed for 512x512, especially because of:
  - circle radius is fixed
  - text labels are fixed size and positioned with a fixed offset from the circle's center
  Fix these and it can work well on other sizes too...

  Args:
    img_data (bytes): The PNG image data as bytes.

  Returns:
    bytes: The modified PNG image data with the overlay drawn.

  """
  w: int
  h: int
  cx: int
  cy: int
  x: int
  y: int
  lw: int
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
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
    return PNGFromRGBImage(img, meta=cast('dict[str, str]', img.info))


def DrawThirdsInfoOverlay(img_data: bytes) -> bytes:
  """Draw an overlay on an image of any size, with target info for moving the zoom frame.

  Overlays:
  - white lines delimiting the 9 sections of the image
  - large green number labels (1-9) centered in each section, left-to-right, top-to-bottom

  Args:
    img_data (bytes): The PNG image data as bytes.

  Returns:
    bytes: The modified PNG image data with the overlay drawn.

  """
  w: int
  h: int
  cx: int
  cy: int
  col: int
  row: int
  lw: int
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
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
    return PNGFromRGBImage(img, meta=cast('dict[str, str]', img.info))


def DrawCrossOverlay(
  img_data: bytes, x: int, y: int, *, col: Color = DEFAULT_MARK_COLOR, lw: int = DEFAULT_MARK_WIDTH
) -> bytes:
  """Draw a cross overlay on an image at the specified coordinates.

  Overlays:
  - a horizontal line spanning the image at the given y-coordinate
  - a vertical line spanning the image at the given x-coordinate

  Args:
    img_data (bytes): The PNG image data as bytes.
    x (int): The x-coordinate of the center of the cross.
    y (int): The y-coordinate of the center of the cross.
    col (Color): The color of the cross; default is DEFAULT_MARK_COLOR.
    lw (int): The line width of the cross in pixels; default is DEFAULT_MARK_WIDTH.

  Returns:
    bytes: The modified PNG image data with the overlay drawn.

  Raises:
    Error: If the coordinates are out of bounds or if there are issues processing the image.

  """
  w: int
  h: int
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
    # check the coords
    draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
    w, h = img.size
    if not (0 <= x < w) or not (0 <= y < h):
      raise Error(f'Invalid coordinates for cross overlay: {x=}, {y=}, image size {w=} x {h=}')
    # draw the cross lines
    draw.line((0, y, w, y), fill=col.value, width=lw)
    draw.line((x, 0, x, h), fill=col.value, width=lw)
    # done, save remembering to add metadata that this image has an overlay
    return PNGFromRGBImage(img, meta=cast('dict[str, str]', img.info))


def RGBImageFromPNG(img_data: bytes) -> PILImage.Image:
  """Decode PNG bytes and return an RGB Pillow image copy.

  Will not convert to RGB if the PNG is not in RGB mode; instead, it will raise an error.

  Args:
    img_data (bytes): The PNG-encoded bytes of the image.

  Returns:
    PILImage.Image: A Pillow Image object in RGB mode.

  Raises:
    Error: on error

  """
  # open
  with PILImage.open(io.BytesIO(img_data)) as img:
    # check mode
    if img.mode != 'RGB':
      raise Error(f'frame mode {img.mode} != RGB')
    # make a copy
    return img.copy()


def RGBImageFromImage(img_data: bytes) -> PILImage.Image:
  """Decode image bytes and return an RGB Pillow image copy. Will convert to RGB if necessary.

  Args:
    img_data (bytes): The image-encoded bytes of the image.

  Returns:
    PILImage.Image: A Pillow Image object in RGB mode.

  """
  # open
  with PILImage.open(io.BytesIO(img_data)) as img:
    # check mode
    if img.mode != 'RGB':
      return img.convert('RGB')
    # make a copy
    return img.copy()


def PNGFromRGBImage(
  img_data: PILImage.Image, *, meta: dict[str, str] | None = None, copy_previous: bool = True
) -> bytes:
  """Encode an RGB Pillow image as PNG bytes.

  Args:
    img_data (PILImage.Image): A Pillow Image object in RGB mode.
    meta (dict[str, str] | None): Optional additional metadata to include in the PNG;
        default is None.
    copy_previous (bool): Whether to copy existing metadata from the original image;
        default is True.

  Returns:
    bytes: The PNG-encoded bytes of the image.

  Raises:
    Error: on error

  """
  # check mode
  if img_data.mode != 'RGB':
    raise Error(f'frame mode {img_data.mode} != RGB')
  # save to PNG bytes
  with io.BytesIO() as buf:
    # embed frame parameters as PNG tEXt metadata chunks; keys use a "tranZoom:" (_app) namespace
    png_meta: PngImagePlugin.PngInfo | None = None
    if meta or (copy_previous and img_data.info.items()):
      png_meta = PngImagePlugin.PngInfo()
      # copy any existing metadata from the original image
      if copy_previous and img_data.info.items():
        for k, v in img_data.info.items():
          if not isinstance(k, str):
            raise Error(f'Unexpected non-string PNG metadata pair: {k!r}: {v!r}')
          png_meta.add_text(k, str(v))
      # add any extra metadata passed in
      if meta:
        for k, v in meta.items():
          png_meta.add_text(k, v)
    # save to PNG bytes
    img_data.save(buf, format='PNG', pnginfo=png_meta)
    return buf.getvalue()


def JPGFromRGBImage(
  img_data: PILImage.Image, *, meta: dict[str, str] | None = None, copy_previous: bool = True
) -> bytes:
  """Encode an RGB Pillow image as JPG bytes.

  Args:
    img_data (PILImage.Image): A Pillow Image object in RGB mode.
    meta (dict[str, str] | None): Optional additional metadata to include in the JPG;
        default is None.
    copy_previous (bool): Whether to copy existing metadata from the original image;
        default is True.

  Returns:
    bytes: The JPG-encoded bytes of the image.

  Raises:
    Error: on error

  """
  # check mode
  if img_data.mode != 'RGB':
    raise Error(f'frame mode {img_data.mode} != RGB')
  # save to JPG bytes
  with io.BytesIO() as buf:
    # store metadata as compact JSON in EXIF ImageDescription (tag 0x010E)
    exif: PILImage.Exif | None = None
    if meta or (copy_previous and img_data.info.items()):
      all_meta: dict[str, str] = {}
      # copy any existing metadata from the original image
      if copy_previous and img_data.info.items():
        for k, v in img_data.info.items():
          if not isinstance(k, str):
            raise Error(f'Unexpected non-string PNG metadata pair: {k!r}: {v!r}')
          all_meta[k] = str(v)
      # add any extra metadata passed in
      if meta:
        all_meta.update(meta)
      # store metadata as compact JSON in EXIF ImageDescription (tag 0x010E)
      # list of tags in: https://github.com/python-pillow/Pillow/blob/main/src/PIL/ExifTags.py
      exif = PILImage.Exif()
      exif[ExifTags.Base.ImageDescription] = json.dumps(all_meta, separators=(',', ':'))
    # save to PNG bytes
    img_data.save(
      buf,
      format='JPEG',
      quality=JPEG_QUALITY,
      optimize=True,
      exif=exif.tobytes() if exif else None,
    )
    return buf.getvalue()


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
