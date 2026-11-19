import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SUBPLAYER_HOME"] = tempfile.mkdtemp()

from subplayer_win import linkimport, sources  # noqa: E402

DATA = Path(__file__).parent / "data"

FEED = """<?xml version="1.0"?><rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>
<title>Radiowissen</title>
<item><title>Urgetreide - Dinkel, Emmer</title><link>https://br.de/a</link><pubDate>Wed, 18 Nov 2026 10:00:00 +0100</pubDate>
<description><![CDATA[<p>Über Getreide</p>]]></description><enclosure url="https://media.br.de/x.mp3" type="audio/mpeg" length="1"/>
<itunes:duration>23:10</itunes:duration></item>
<item><title>Nur Text</title><link>https://br.de/b</link></item>
<item><title>Ein Video</title><enclosure url="https://cdn.example.org/v/clip.mp4?x=1" type="video/mp4"/></item>
<item><title>Bei YouTube</title><enclosure url="https://www.youtube.com/watch?v=abc" type="video/mp4"/></item>
</channel></rss>"""


class Telegram(unittest.TestCase):
    def test_names(self):
        self.assertEqual(sources.telegram_name("t.me/bbcpersian"), "bbcpersian")
        self.assertEqual(sources.telegram_name("https://t.me/s/bbcpersian/295717"), "bbcpersian")
        self.assertEqual(sources.telegram_name("@euronewspe"), "euronewspe")
        self.assertIsNone(sources.telegram_name("t.me/+AbCdEf"))
        self.assertIsNone(sources.telegram_name("https://example.org"))
        with self.assertRaises(ValueError):
            sources.detect("https://t.me/+AbCdEfGh")

    def test_real_channel_page(self):
        page = (DATA / "tg-channel.html").read_text(encoding="utf-8")
        films = sources.telegram_posts(page, "bbcpersian", "BBCPersian")
        self.assertGreaterEqual(len(films), 3)
        f = films[0]
        self.assertEqual(f.channel, "Telegram")
        self.assertTrue(f.url_website.startswith("https://t.me/bbcpersian/"))
        self.assertEqual(f.url_video, "")                    # fetched fresh when downloading
        self.assertGreater(f.duration, 0)
        self.assertGreater(f.timestamp, 1_700_000_000)
        self.assertTrue(f.title and "<" not in f.title)
        self.assertEqual(sources._tg_title(page), "BBCPersian")


class Feeds(unittest.TestCase):
    def test_feed_items(self):
        films = sources._feed_items(FEED, sources.Source("https://br.de/feed", "Radiowissen", "feed"))
        self.assertEqual([f.title for f in films], ["Urgetreide - Dinkel, Emmer", "Ein Video"])    # no text-only, no YouTube
        self.assertEqual(films[0].duration, 23 * 60 + 10)
        self.assertEqual(films[0].description, "Über Getreide")
        self.assertGreater(films[0].timestamp, 0)
        self.assertEqual(sources._feed_title(FEED), "Radiowissen")

    def test_feed_link_in_page(self):
        page = '<html><head><link rel="alternate" type="application/rss+xml" title="x" href="/podcast/feed.xml"></head></html>'
        self.assertEqual(sources._feed_link(page, "https://example.org/sendung/"), "https://example.org/podcast/feed.xml")

    def test_page_qualities_grouped(self):
        names = ["webs", "webm", "webl", "webxl"]
        page = " ".join(f'"https://cdn.ard.de/video/2026/1119/TV-20261119-1437-4800.{q}.h264.mp4"' for q in names)
        page += ' "https://cdn.ard.de/video/other_720p.mp4" "https://cdn.ard.de/video/other_360p.mp4"'

        class R:
            text = "<title>tagesschau in 100 Sekunden</title>" + page
            def raise_for_status(self): pass
        real = sources._get
        sources._get = lambda *a, **k: R()
        try:
            films = sources.page_videos(sources.Source("https://tagesschau.de/x", "100 Sekunden", "page"))
        finally:
            sources._get = real
        self.assertEqual(len(films), 2)
        self.assertIn(".webl.", films[0].url_video)
        self.assertIn("_720p", films[1].url_video)

    def test_search_words(self):
        films = sources._feed_items(FEED, sources.Source("https://br.de/feed", "Radiowissen", "feed"))
        self.assertTrue(sources.matches(films[0], "getreide dinkel"))
        self.assertFalse(sources.matches(films[0], "getreide auto"))


class Refused(unittest.TestCase):
    def test_youtube(self):
        with self.assertRaises(ValueError):
            sources.detect("https://www.youtube.com/@tagesschau")

    def test_telegram_link_resolves_fresh(self):
        real = sources.fresh_video
        sources.fresh_video = lambda u, s=None: "https://cdn4.telesco.pe/file/x.mp4?token=1"
        try:
            f = linkimport.resolve("https://t.me/bbcpersian/295717")
        finally:
            sources.fresh_video = real
        self.assertEqual(f.video_url, "https://cdn4.telesco.pe/file/x.mp4?token=1")
        sources.fresh_video = lambda u, s=None: ""
        try:
            with self.assertRaises(ValueError):
                linkimport.resolve("https://t.me/bbcpersian/295717")
        finally:
            sources.fresh_video = real


if __name__ == "__main__":
    unittest.main()
