"""Core WebVTT parsing and serialization.

Design decisions:

* The parser is line-oriented.  WebVTT is a line-based format and the only
  multi-line structures are cue payloads and STYLE blocks.  Keeping the
  parser line-oriented makes it easy to reason about and to test.
* Cue payloads are stored as a list of lines rather than a single string.
  This preserves blank lines inside a cue and makes serialization exact.
  Joining with ``\n`` would lose information about a trailing blank line.
* STYLE blocks are kept verbatim as a list of lines.  They are not parsed
  further because the spec leaves their contents to the renderer.
* The parser is lenient: a missing ``WEBVTT`` header, missing blank lines
  between cues, and trailing whitespace are tolerated.  A strict parser
  would reject many real-world files; the trade-off is that malformed
  input may be accepted silently.
* Timestamps are parsed into milliseconds since the start of the video.
  This avoids floating-point comparisons and is the unit used by most
  players.  ``None`` is used for missing timestamps (e.g. a cue that
  only has a start time is invalid, so both are required).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

__all__ = ["Cue", "parse_vtt", "serialize_vtt"]

# Matches a WebVTT timestamp: HH:MM:SS.mmm or MM:SS.mmm.
_TIMESTAMP_RE = re.compile(
    r"^(?:(?P<hours>\d{2,}):)?(?P<minutes>\d{2}):(?P<seconds>\d{2})\.(?P<millis>\d{3})$"
)


def _parse_timestamp(text: str) -> int:
    """Parse a WebVTT timestamp into milliseconds.

    Raises ValueError if the timestamp is not well-formed.
    """
    match = _TIMESTAMP_RE.match(text.strip())
    if not match:
        raise ValueError(f"invalid timestamp: {text!r}")
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis = int(match.group("millis"))
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"timestamp out of range: {text!r}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def _format_timestamp(ms: int) -> str:
    """Format milliseconds as a WebVTT timestamp (HH:MM:SS.mmm)."""
    if ms < 0:
        raise ValueError("timestamp cannot be negative")
    millis = ms % 1000
    total_seconds = ms // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


@dataclass
class Cue:
    """A single WebVTT cue.

    Attributes:
        identifier: optional cue identifier (the line before the timestamp).
        start: start time in milliseconds.
        end: end time in milliseconds.
        payload: list of text lines.  An empty list means the cue has no
            text; this is distinct from a cue containing a single empty
            line, which is represented as ``[""]``.
    """

    start: int
    end: int
    payload: List[str] = field(default_factory=list)
    identifier: Optional[str] = None

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError("cue times cannot be negative")
        if self.end < self.start:
            raise ValueError("cue end time cannot be before start time")


def parse_vtt(text: str) -> Tuple[List[Cue], List[List[str]]]:
    """Parse a WebVTT string.

    Returns a tuple ``(cues, styles)`` where ``cues`` is a list of
    :class:`Cue` objects and ``styles`` is a list of STYLE blocks, each
    represented as a list of lines (excluding the ``STYLE`` line itself).

    The parser is intentionally lenient: it accepts a missing header and
    missing blank lines between cues.  It raises ``ValueError`` only when
    a timestamp cannot be parsed or a cue has no timestamp.
    """
    lines = text.splitlines()
    cues: List[Cue] = []
    styles: List[List[str]] = []

    i = 0
    n = len(lines)

    # Skip an optional BOM and the WEBVTT header line.
    if i < n and lines[i].startswith("\ufeff"):
        lines[i] = lines[i][1:]
    if i < n and lines[i].strip() == "WEBVTT":
        i += 1
    # Skip any header metadata (lines until the first blank line).
    while i < n and lines[i].strip() != "":
        # A header line that looks like a timestamp means the file has no
        # header metadata and we are already at the first cue.
        if _TIMESTAMP_RE.match(lines[i].strip().split(" ")[0]):
            break
        i += 1
    # Skip blank lines after the header.
    while i < n and lines[i].strip() == "":
        i += 1

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped == "":
            i += 1
            continue

        if stripped == "STYLE":
            i += 1
            style_lines: List[str] = []
            while i < n and lines[i].strip() != "":
                style_lines.append(lines[i])
                i += 1
            styles.append(style_lines)
            continue

        # Determine whether this line is an identifier or a timestamp.
        identifier: Optional[str] = None
        timestamp_line = stripped
        if "-->" not in stripped:
            identifier = stripped
            i += 1
            if i >= n:
                raise ValueError("cue identifier without timestamp")
            timestamp_line = lines[i].strip()

        if "-->" not in timestamp_line:
            raise ValueError(f"expected timestamp, got: {timestamp_line!r}")

        start_text, _, end_text = timestamp_line.partition("-->") 
        # The end timestamp may be followed by cue settings; ignore them.
        end_text = end_text.strip().split(" ")[0]
        start = _parse_timestamp(start_text.strip())
        end = _parse_timestamp(end_text)

        i += 1
        payload: List[str] = []
        while i < n and lines[i].strip() != "":
            payload.append(lines[i])
            i += 1

        cues.append(Cue(start=start, end=end, payload=payload, identifier=identifier))

    return cues, styles


def serialize_vtt(cues: List[Cue], styles: Optional[List[List[str]]] = None) -> str:
    """Serialize cues and optional STYLE blocks to a WebVTT string.

    The output always starts with the ``WEBVTT`` header followed by a
    blank line.  Cues are separated by blank lines.  STYLE blocks are
    written before the cues, each followed by a blank line.
    """
    parts: List[str] = ["WEBVTT", ""]

    if styles:
        for style in styles:
            parts.append("STYLE")
            parts.extend(style)
            parts.append("")

    for cue in cues:
        if cue.identifier is not None:
            parts.append(cue.identifier)
        parts.append(f"{_format_timestamp(cue.start)} --> {_format_timestamp(cue.end)}")
        parts.extend(cue.payload)
        parts.append("")

    # Remove the trailing blank line; the file should end with a newline.
    if parts and parts[-1] == "":
        parts.pop()

    return "\n".join(parts) + "\n"
