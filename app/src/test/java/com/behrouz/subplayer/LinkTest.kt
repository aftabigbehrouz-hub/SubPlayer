package com.behrouz.subplayer

import com.behrouz.subplayer.net.LinkImporter
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LinkTest {
    @Test fun picksMediumQualityMp4FromTagesschauStylePage() {
        val html = """<html><head><meta property="og:title" content="tagesschau 20:00 Uhr"><title>x</title></head>
            <script>{"streams":{"h264s":"https:\/\/media.tagesschau.de\/video\/2026\/1113\/TV-20261113-2000-0001.webs.h264.mp4",
            "h264m":"https:\/\/media.tagesschau.de\/video\/2026\/1113\/TV-20261113-2000-0001.webm.h264.mp4",
            "h264l":"https://media.tagesschau.de/video/2026/1113/TV-20261113-2000-0001.webl.h264.mp4",
            "h264xxl":"https://media.tagesschau.de/video/2026/1113/TV-20261113-2000-0001.webxxl.h264.mp4",
            "adaptive":"https://adaptive.tagesschau.de/i/video/x.m3u8"}}</script></html>"""
        val f = LinkImporter.findInPage(html)!!
        assertEquals("https://media.tagesschau.de/video/2026/1113/TV-20261113-2000-0001.webl.h264.mp4", f.videoUrl)
        assertEquals("tagesschau 20:00 Uhr", f.title)
    }

    @Test fun webmQualityNameIsNotCutShort() {
        val f = LinkImporter.findInPage("""src="https://x.de/v/TV-1.webm.h264.mp4" """)!!
        assertEquals("https://x.de/v/TV-1.webm.h264.mp4", f.videoUrl)
    }

    @Test fun nothingFound() {
        assertNull(LinkImporter.findInPage("<html>no video here</html>"))
    }
}
