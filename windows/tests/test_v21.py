"""Windows 2.1: broadcaster subtitles, catalogue entries, link matching, proxy settings."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subplayer_win import linkimport as L      # noqa: E402
from subplayer_win import mediathek as M       # noqa: E402
from subplayer_win import netcfg, subtitles    # noqa: E402

TTML_ARD = """<?xml version="1.0" encoding="UTF-8"?>
<tt:tt xmlns:tt="http://www.w3.org/ns/ttml" xmlns:tts="http://www.w3.org/ns/ttml#styling"
       xmlns:ttp="http://www.w3.org/ns/ttml#parameter" ttp:timeBase="media" ttp:frameRate="25">
 <tt:body><tt:div>
  <tt:p begin="10:00:01.240" end="10:00:03.000"><tt:span tts:color="#FFFFFF">Guten Abend,</tt:span><tt:br/>
   <tt:span tts:color="#FFFF00">meine Damen und Herren.</tt:span></tt:p>
  <tt:p begin="10:00:04:12" end="10:00:06:00"><tt:span>*</tt:span></tt:p>
  <tt:p begin="10:00:06.500" end="10:00:08.000"><tt:span>Das Wetter:</tt:span></tt:p>
 </tt:div></tt:body></tt:tt>"""

TTML_TICKS = """<tt xmlns="http://www.w3.org/ns/ttml" xmlns:ttp="http://www.w3.org/ns/ttml#parameter" ttp:tickRate="10000000">
<body><div><p begin="12400000t" end="30000000t">Hallo   Welt</p><p begin="3.5s" dur="1500ms">zwei</p></div></body></tt>"""


class BroadcasterSubtitles(unittest.TestCase):
    def test_ebu_tt_with_10h_timecode_and_frames(self):
        cues = subtitles.parse_any(TTML_ARD)
        self.assertEqual([c.start_ms for c in cues], [1240, 6500])          # the "*" sound line is dropped
        self.assertEqual(cues[0].text, "Guten Abend,\nmeine Damen und Herren.")
        self.assertEqual(cues[0].end_ms, 3000)

    def test_ticks_seconds_and_duration(self):
        cues = subtitles.parse_any(TTML_TICKS)
        self.assertEqual([(c.start_ms, c.end_ms, c.text) for c in cues], [(1240, 3000, "Hallo Welt"), (3500, 5000, "zwei")])

    def test_frames_conversion(self):
        x = TTML_ARD.replace('begin="10:00:06.500"', 'begin="10:00:06:20"')
        self.assertEqual(subtitles.parse_any(x)[1].start_ms, 6800)           # 20 frames at 25 fps

    def test_vtt_and_srt_still_work(self):
        self.assertEqual(subtitles.parse_any("WEBVTT\n\n00:00:01.000 --> 00:00:02.500\n<c.yellow>Hallo</c>\n")[0].text, "Hallo")
        self.assertEqual(len(subtitles.parse_any("1\n00:00:01,000 --> 00:00:02,000\nEins\n\n2\n00:00:03,000 --> 00:00:04,000\nZwei\n")), 2)

    def test_language_guess(self):
        de = [subtitles.Cue(0, 1, "Ich habe das nicht gewusst, aber es ist auch egal und wir gehen.")]
        en = [subtitles.Cue(0, 1, "I did not know that, but it is fine and we are going to the park.")]
        self.assertEqual(subtitles.guess_lang(de), "de")
        self.assertEqual(subtitles.guess_lang(en), "en")


ENTRY = {"channel": "ZDF", "topic": "Terra X", "title": "Mansa Musa und das goldene Reich", "description": "Doku",
         "timestamp": 1794700000, "duration": 2580, "size": 870000000,
         "url_website": "https://www.zdf.de/video/dokus/terra-x-100/mansa-musa-100",
         "url_subtitle": "http://utstreaming.zdf.de/mtt/zdf/26/11/x.xml",
         "url_video": "https://nrodlzdf-a.akamaihd.net/none/zdf/26/11/x/1/x_3360k_p36v17.mp4",
         "url_video_low": "60|808k_p11v17.mp4", "url_video_hd": "https://nrodlzdf-a.akamaihd.net/none/zdf/26/11/x/1/x_6660k_p37v17.mp4"}


class Catalogue(unittest.TestCase):
    def test_entry_and_shortened_links(self):
        f = M.film_from(ENTRY)
        self.assertEqual(f.url_video_low, ENTRY["url_video"][:60] + "808k_p11v17.mp4")
        self.assertTrue(f.url_subtitle.startswith("https://"))
        self.assertEqual(f.video("hd"), ENTRY["url_video_hd"])
        self.assertEqual(f.label, "ZDF")
        self.assertEqual(f.length, "43 min")
        self.assertTrue(f.has_subtitles)

    def test_response_and_dedupe(self):
        dup = dict(ENTRY, channel="3Sat")
        films, total = M.parse_response({"result": {"results": [ENTRY, dup], "queryInfo": {"totalResults": 2}}, "err": None})
        self.assertEqual(total, 2)
        self.assertEqual(len(M.dedupe(films)), 1)
        with self.assertRaises(IOError):
            M.parse_response({"err": ["bad query"], "result": None})

    def test_query(self):
        q = M.build_query("terra x", ["ZDF", "3sat"], length=(900, 2700), offset=30, size=10)
        self.assertEqual(q["queries"][0], {"fields": ["title", "topic"], "query": "terra x"})
        self.assertIn({"fields": ["channel"], "query": "3sat"}, q["queries"])
        self.assertEqual((q["duration_min"], q["duration_max"], q["offset"], q["size"]), (900, 2700, 30, 10))
        json.dumps(q)

    def test_programme_names_from_addresses(self):
        self.assertEqual(M._url_topics("https://www.zdf.de/video/reportagen/backstage-154/dr-nice-100"), ["backstage"])
        self.assertIn("phoenix persönlich",
                      M._url_topics("https://www.phoenix.de/sendungen/gespraeche/phoenix-persoenlich/claudia-major-a-5241011.html"))

    def test_title_queries(self):
        qs = M._title_queries("Universitäten der Welt - Stanford University - Die ganze Doku | ARTE")
        self.assertEqual(qs[0], "Universitäten der Welt Stanford University Die ganze")
        self.assertIn("Stanford University", qs)

    def test_exact_match(self):
        f = M.film_from(ENTRY)
        self.assertIs(M._exact([f], M._norm_url("https://zdf.de/video/dokus/terra-x-100/mansa-musa-100/?x=1"), "mansa-musa-100"), f)


class Links(unittest.TestCase):
    def test_refused_and_broadcasters(self):
        self.assertIn("YouTube", L.refused_reason("https://youtu.be/abc"))
        self.assertIsNone(L.refused_reason("https://www.ardmediathek.de/video/x"))
        for u in ("https://www.zdf.de/a", "https://www.arte.tv/de/videos/1", "https://p.dw.com/p/5PKK8", "https://www.kika.de/x"):
            self.assertTrue(L.is_broadcaster(u), u)
        self.assertFalse(L.is_broadcaster("https://example.com/video.html"))

    def test_ard_and_arte_ids(self):
        self.assertEqual(L.ard_id("https://www.ardmediathek.de/video/quarks/schlaf/wdr/Y3JpZDovL3dkci5kZS9CZWl0"), "Y3JpZDovL3dkci5kZS9CZWl0")
        self.assertIsNone(L.ard_id("https://www.ardmediathek.de/sendung/die-sendung-mit-der-maus/abc"))
        self.assertEqual(L.ARTE_ID.search("https://www.arte.tv/de/videos/128830-009-A/twist/").group(2), "128830-009-A")

    def test_mp4_choice_skips_alternative_versions(self):
        c = [("https://x/DE_klaresprache_1280x720.mp4", 720), ("https://x/DE_sendeton_640x360.mp4", 360),
             ("https://x/DE_sendeton_1280x720.mp4", 720), ("https://x/DE_sendeton_1920x1080.mp4", 1080),
             ("https://x/DE_audiodeskription_960x540.mp4", 540)]
        self.assertEqual(L._pick_mp4(c), "https://x/DE_sendeton_1280x720.mp4")

    def test_direct_and_stream_links(self):
        self.assertFalse(L.resolve("https://cdn.example.org/a/clip.mp4").hls)
        self.assertTrue(L.resolve("https://cdn.example.org/a/master.m3u8?x=1").hls)


class Proxy(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in netcfg.VARS + ("NO_PROXY", "no_proxy")}

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_normalise_and_validate(self):
        self.assertEqual(netcfg.normalise("127.0.0.1:10809"), "http://127.0.0.1:10809")
        self.assertEqual(netcfg.normalise("127.0.0.1:10808", "socks5"), "socks5h://127.0.0.1:10808")
        self.assertTrue(netcfg.valid("127.0.0.1:10809"))
        self.assertFalse(netcfg.valid("10809"))
        self.assertFalse(netcfg.valid("not a proxy"))

    def test_apply_modes(self):
        self.assertIn("through the proxy", netcfg.apply({"net_mode": "proxy", "net_proxy": "127.0.0.1:10809"}))
        self.assertEqual(os.environ["HTTPS_PROXY"], "http://127.0.0.1:10809")
        self.assertEqual(netcfg.ffmpeg_proxy(), "http://127.0.0.1:10809")
        netcfg.apply({"net_mode": "direct"})
        self.assertNotIn("HTTPS_PROXY", os.environ)
        self.assertEqual(os.environ["NO_PROXY"], "*")
        netcfg.apply({"net_mode": "proxy", "net_proxy": "127.0.0.1:10808", "net_kind": "socks5"})
        self.assertEqual(netcfg.ffmpeg_proxy(), "")                      # FFmpeg can't use SOCKS
        netcfg.apply({"net_mode": "system"})
        self.assertNotIn("NO_PROXY", os.environ)


if __name__ == "__main__":
    unittest.main()
