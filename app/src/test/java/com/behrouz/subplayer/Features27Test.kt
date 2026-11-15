package com.behrouz.subplayer

import com.behrouz.subplayer.learn.Levels
import com.behrouz.subplayer.learn.Library
import com.behrouz.subplayer.net.Catalog
import com.behrouz.subplayer.subs.Cue
import com.behrouz.subplayer.subs.Srt
import com.behrouz.subplayer.subs.Ttml
import com.behrouz.subplayer.ui.fmtMs
import com.behrouz.subplayer.ui.parseMs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Version 2.7: broadcaster subtitles, word levels, the library ("where else"), the catalogue, time fields. */
class Features27Test {

    @Test fun ttmlWithBroadcastOffsetAndLineBreaks() {
        val xml = """<?xml version="1.0" encoding="UTF-8"?>
            <tt:tt xmlns:tt="http://www.w3.org/ns/ttml" ttp:frameRate="25" xmlns:ttp="http://www.w3.org/ns/ttml#parameter">
            <tt:body><tt:div>
              <tt:p begin="10:00:01.000" end="10:00:03.500"><tt:span style="s1">Guten Abend,</tt:span><tt:br/><tt:span>meine Damen &amp; Herren.</tt:span></tt:p>
              <tt:p begin="10:00:04:12" end="10:00:06:00"><tt:span>Zweite Zeile</tt:span></tt:p>
            </tt:div></tt:body></tt:tt>"""
        val c = Ttml.parse(xml)
        assertEquals(2, c.size)
        assertEquals(1000L, c[0].startMs)
        assertEquals(3500L, c[0].endMs)
        assertEquals("Guten Abend,\nmeine Damen & Herren.", c[0].text)
        assertEquals(4480L, c[1].startMs)          // 12 frames at 25 fps = 480 ms
    }

    @Test fun ttmlTicksAndParseAnyFallsBackToSrt() {
        val xml = """<tt xmlns="http://www.w3.org/ns/ttml" ttp:tickRate="10000000"><body><div>
            <p begin="10000000t" end="25000000t">Hallo</p></div></body></tt>"""
        val c = Ttml.parseAny(xml)
        assertEquals(1000L, c[0].startMs); assertEquals(2500L, c[0].endMs)
        val srt = Ttml.parseAny("1\n00:00:01,000 --> 00:00:02,000\nHi there\n")
        assertEquals("Hi there", srt[0].text)
        val vtt = Ttml.parseAny("WEBVTT\n\n00:01.000 --> 00:02.500 align:start\nHello\n")
        assertEquals(1000L, vtt[0].startMs); assertEquals("Hello", vtt[0].text)
    }

    @Test fun guessesLanguage() {
        assertEquals("de", Ttml.guessLang(listOf(Cue(0, 1, "Ich weiß nicht, ob das und die Sache noch geht."))))
        assertEquals("en", Ttml.guessLang(listOf(Cue(0, 1, "I don't know if that is the thing and you are with us."))))
    }

    @Test fun levelsUseTheLowestBaseWordAndC2ForKnownRareWords() {
        val lv = Levels { name -> if (name == "levels-de.tsv") "ich\t1\ngehen\t1\nmich\t3\ngestalten\t3\nbankrott\t5\n" else null }
        assertEquals(1, lv.level("ich", "de"))
        // "mich" is B1 in the list on its own, but its base word "ich" is A1
        assertEquals(1, lv.level("mich", "de") { listOf("ich") })
        assertEquals(3, lv.level("gestaltet", "de") { listOf("gestalten") })
        assertEquals(6, lv.level("Zwickmühle", "de") { listOf("Zwickmühle") })      // in the dictionary, in no list
        assertEquals(0, lv.level("2026", "de"))
        assertEquals(0, lv.level("Xyzzy", "de"))
        assertEquals("C2", Levels.NAMES[6]); assertEquals(7, Levels.COLORS.size)
    }

    @Test fun vocabularyKeepsNounsAndLowercasesSentenceStarts() {
        val cues = listOf(Cue(0, 1, "Ich gehe heute ins Kino."), Cue(1, 2, "Das Kino ist groß. Ich gehe gern."), Cue(2, 3, "Heute ist schön."))
        val v = Library.vocabulary(cues, "de").associateBy { it.shown }
        assertEquals(2, v["Kino"]?.count)        // capitalised mid-sentence: a noun
        assertEquals(2, v["ich"]?.count)         // only ever at sentence starts: not the noun "das Ich"
        assertEquals(2, v["heute"]?.count)
        assertEquals(1, Library.firstLine(cues, "groß"))
    }

    @Test fun libraryFindsUsesOfAllFormsAndSkipsTranslations() {
        val dir = Files.createTempDirectory("subs").toFile(); val synced = Files.createTempDirectory("synced").toFile()
        File(dir, "Film_A_1a2b.de.srt").writeText(Srt.write(listOf(Cue(1000, 2000, "Warum ging er?"), Cue(3000, 4000, "Wir gehen jetzt."))))
        File(dir, "Film_A_1a2b.de.tr-fa.srt").writeText(Srt.write(listOf(Cue(1000, 2000, "چرا"))))
        File(synced, "Film_B.de.srt").writeText(Srt.write(listOf(Cue(500, 900, "Er geht nach Hause."))))
        File(synced, "Film_B.en.srt").writeText(Srt.write(listOf(Cue(500, 900, "He goes home."))))
        val items = Library.scan(dir, synced, mapOf("Film_A" to ("content://a" to "Film A.mp4")))
        assertEquals(3, items.size)
        assertEquals("content://a", items.first { it.key == "Film_A" }.uri)
        val (uses, n) = Library.findUses("gehen", "de", items, setOf("gehen", "geht", "ging", "gegangen"))
        assertEquals(2, n)
        assertEquals(3, uses.size)
        val first = uses.first { it.text.startsWith("Warum") }
        assertEquals("ging", first.text.substring(first.spans[0]))
        val (p, _) = Library.findUses("nach Hause", "de", items, emptySet())
        assertEquals(1, p.size)
    }

    @Test fun catalogueQueryAndResponse() {
        val q = org.json.JSONObject(Catalog.buildQuery(topic = "Terra X", channels = listOf("ZDF"), minSec = 60, size = 8))
        assertEquals("zdf", q.getJSONArray("queries").getJSONObject(1).getString("query"))
        assertEquals(60, q.getInt("duration_min"))
        val json = """{"err":null,"result":{"results":[
            {"channel":"ZDF","topic":"Terra X","title":"Die Alpen","description":"…","timestamp":1700000000,"duration":2580,
             "url_website":"https://www.zdf.de/x.html","url_subtitle":"http://utstreaming.zdf.de/a.xml","url_video":"http://rodl.zdf.de/a_808k.mp4",
             "url_video_hd":"27|3360k.mp4"},
            {"channel":"3Sat","topic":"Terra X","title":"Die Alpen","duration":2590,"url_video":"https://x/b.mp4"}],
            "queryInfo":{"totalResults":42}}}"""
        val (films, total) = Catalog.parseResponse(json)
        assertEquals(42, total)
        assertEquals(1, films.size)                         // same programme twice → kept once
        assertEquals("https://rodl.zdf.de/a_808k.mp4", films[0].urlVideo)
        assertEquals("https://utstreaming.zdf.de/a.xml", films[0].urlSubtitle)
        assertEquals("43 min", films[0].length)
        assertEquals("http://rodl.zdf.de/a_3360k.mp4", Catalog.full("http://rodl.zdf.de/a_808k.mp4", "21|3360k.mp4"))
    }

    @Test fun podcastFeedAndPageTopics() {
        val rss = """<rss><channel><title>6 Minute English</title>
            <item><title>Is it OK to be lazy?</title><description><![CDATA[<p>Neil and Beth</p>]]></description>
            <pubDate>Thu, 13 Nov 2025 08:00:00 GMT</pubDate><itunes:duration>6:12</itunes:duration>
            <enclosure url="https://open.live.bbc.co.uk/x.mp3?a=1&amp;b=2" type="audio/mpeg"/></item></channel></rss>"""
        val f = Catalog.parsePodcast(rss, "BBC")
        assertEquals(1, f.size)
        assertEquals("https://open.live.bbc.co.uk/x.mp3?a=1&b=2", f[0].urlVideo)
        assertEquals(372, f[0].duration)
        assertTrue(f[0].audio)
        assertEquals("Neil and Beth", f[0].description)
        assertTrue("phoenix persönlich" in Catalog.urlTopics("https://www.phoenix.de/sendungen/gespraeche/phoenix-persoenlich/abc-123.html"))
        assertEquals("Terra X Die Alpen", Catalog.titleQueries("Terra X: Die Alpen | ZDFmediathek")[0])
    }

    @Test fun timeFields() {
        assertEquals("1:02.500", fmtMs(62_500))
        assertEquals(62_500L, parseMs("1:02.5"))
        assertEquals(3_723_004L, parseMs("1:02:03.004"))
        assertEquals(7_000L, parseMs("7"))
        assertNull(parseMs("abc"))
    }
}
