"""A small, dependency-free WebVTT parser and serializer.

Public API:
    Cue         - a single subtitle cue
    parse_vtt   - parse a WebVTT string into a list of Cue objects
    serialize_vtt - serialize a list of Cue objects into a WebVTT string
"""

from .core import Cue, parse_vtt, serialize_vtt

__all__ = ["Cue", "parse_vtt", "serialize_vtt"]
