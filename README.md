# tiny_vtt_subtitle

A dependency-free WebVTT parser and serializer for Python.

## Usage

```python
from tiny_vtt_subtitle import parse_vtt, serialize_vtt, Cue

text = """WEBVTT

intro
00:00:01.000 --> 00:00:02.000
Hello

00:00:03.000 --> 00:00:04.000
World
"""

cues, styles = parse_vtt(text)
print(cues[0].identifier)  # "intro"
print(cues[0].payload)     # ["Hello"]

output = serialize_vtt(cues, styles)
print(output)
```

## Why this exists

WebVTT files are common in video pipelines, but many parsers either pull in
large dependencies or silently drop cue identifiers and STYLE blocks.  This
library keeps the surface small and the data model transparent: a cue is a
dataclass with integer millisecond timestamps and a list of payload lines, and
STYLE blocks are preserved verbatim.  The trade-off is that the parser is
lenient: it accepts missing headers and missing blank lines, so malformed files
may not raise an error.  Strict validation is left to the caller.

## Awkward edge

Cue payloads are stored as a list of lines.  An empty payload is `[]`, while a
payload containing a single empty line is `[""]`.  Serializing a cue with an
empty payload produces a cue with no text line, which round-trips correctly.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

