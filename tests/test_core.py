"""Tests for tiny_vtt_subtitle.

These tests cover the happy path plus the awkward cases the parser
actually handles: missing headers, cue identifiers, STYLE blocks,
multi-line payloads, and malformed timestamps.
"""

import unittest

from tiny_vtt_subtitle import Cue, parse_vtt, serialize_vtt


class TestParseVtt(unittest.TestCase):
    def test_simple_cue(self):
        text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n"
        cues, styles = parse_vtt(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].start, 1000)
        self.assertEqual(cues[0].end, 2000)
        self.assertEqual(cues[0].payload, ["Hello"])
        self.assertIsNone(cues[0].identifier)
        self.assertEqual(styles, [])

    def test_cue_identifier(self):
        text = "WEBVTT\n\nintro\n00:00:01.000 --> 00:00:02.000\nHello\n"
        cues, _ = parse_vtt(text)
        self.assertEqual(cues[0].identifier, "intro")

    def test_multiline_payload(self):
        text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nLine one\nLine two\n"
        cues, _ = parse_vtt(text)
        self.assertEqual(cues[0].payload, ["Line one", "Line two"])

    def test_style_block(self):
        text = (
            "WEBVTT\n\n"
            "STYLE\n"
            "::cue { color: yellow; }\n"
            "\n"
            "00:00:01.000 --> 00:00:02.000\nHello\n"
        )
        cues, styles = parse_vtt(text)
        self.assertEqual(styles, [["::cue { color: yellow; }"]])
        self.assertEqual(len(cues), 1)

    def test_missing_header(self):
        text = "00:00:01.000 --> 00:00:02.000\nHello\n"
        cues, _ = parse_vtt(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].payload, ["Hello"])

    def test_short_timestamp(self):
        text = "WEBVTT\n\n01:02.345 --> 01:03.456\nHello\n"
        cues, _ = parse_vtt(text)
        self.assertEqual(cues[0].start, 62345)
        self.assertEqual(cues[0].end, 63456)

    def test_invalid_timestamp_raises(self):
        text = "WEBVTT\n\nnot a timestamp\nHello\n"
        with self.assertRaises(ValueError):
            parse_vtt(text)

    def test_out_of_range_timestamp_raises(self):
        text = "WEBVTT\n\n00:60:00.000 --> 00:61:00.000\nHello\n"
        with self.assertRaises(ValueError):
            parse_vtt(text)


class TestSerializeVtt(unittest.TestCase):
    def test_round_trip(self):
        original = (
            "WEBVTT\n\n"
            "intro\n"
            "00:00:01.000 --> 00:00:02.000\n"
            "Hello\n"
            "\n"
            "00:00:03.000 --> 00:00:04.000\n"
            "World\n"
        )
        cues, styles = parse_vtt(original)
        output = serialize_vtt(cues, styles)
        self.assertEqual(output, original)

    def test_serialize_style(self):
        cues = [Cue(start=1000, end=2000, payload=["Hi"])]
        styles = [["::cue { color: yellow; }", "::cue(b) { font-weight: bold; }"]]
        output = serialize_vtt(cues, styles)
        expected = (
            "WEBVTT\n\n"
            "STYLE\n"
            "::cue { color: yellow; }\n"
            "::cue(b) { font-weight: bold; }\n"
            "\n"
            "00:00:01.000 --> 00:00:02.000\n"
            "Hi\n"
        )
        self.assertEqual(output, expected)

    def test_serialize_no_payload(self):
        cue = Cue(start=0, end=1000)
        output = serialize_vtt([cue])
        self.assertEqual(output, "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n")

    def test_negative_time_raises(self):
        with self.assertRaises(ValueError):
            Cue(start=-1, end=1000)
        with self.assertRaises(ValueError):
            Cue(start=1000, end=500)


if __name__ == "__main__":
    unittest.main()
