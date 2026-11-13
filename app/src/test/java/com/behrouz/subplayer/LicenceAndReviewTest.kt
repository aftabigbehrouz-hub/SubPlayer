package com.behrouz.subplayer

import com.behrouz.subplayer.licence.Base32
import com.behrouz.subplayer.licence.Licence
import com.behrouz.subplayer.words.SavedWord
import com.behrouz.subplayer.words.Srs
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LicenceAndReviewTest {

    // Made by licence-tool/make_activation_code.py with the owner's private key
    private val pcCode = "KNIDC7CBIIYTEQZNIRCTGNCGPRKGK43UEBBHK6LFOIQNROOZQTNYY.GBCQEIIAQWA6CMMWEK3NKNQRRQLUY2FTDQLUFPDQFMAATELEYSPQ6K63N33QEICD7AXGWVB74A5P7DAJDD7TIY2NL3ZRCEPMEJMEPNIIJ3VRS4QEUU"

    @Test fun acceptsCodeFromPcToolOnItsPhone() {
        assertEquals("Test Buyer علی", Licence.verify(pcCode, "AB12C-DE34F")?.name)
        assertEquals("Test Buyer علی", Licence.verify(" " + pcCode.lowercase() + "\n", "ab12c-de34f")?.name)
    }

    @Test fun rejectsOtherPhoneAndTampering() {
        assertNull(Licence.verify(pcCode, "ZZZZZ-ZZZZZ"))
        val tampered = "A" + pcCode.drop(1)
        assertNull(Licence.verify(tampered, "AB12C-DE34F"))
        assertNull(Licence.verify("nonsense", "AB12C-DE34F"))
    }

    @Test fun deviceCodeFormat() {
        val c = Licence.codeFor("1234567890abcdef")
        assertTrue(Regex("[A-Z2-7]{5}-[A-Z2-7]{5}").matches(c))
        assertEquals(c, Licence.codeFor("1234567890abcdef"))
    }

    @Test fun base32RoundTrip() {
        val data = ByteArray(200) { (it * 37 + 11).toByte() }
        assertArrayEquals(data, Base32.decode(Base32.encode(data)))
    }

    private fun word() = SavedWord(text = "ging", lemma = "gehen", sentence = "Er ging nach Hause.",
        videoUri = "content://v", videoName = "v.mp4", startMs = 1000, endMs = 3000, created = 0, due = 0)

    @Test fun gotItMovesUpAndSpacesOut() {
        val day = 86_400_000L
        var w = word()
        val expected = listOf(1, 2, 4, 7, 15, 30, 60, 60)
        for ((i, days) in expected.withIndex()) {
            w = Srs.review(w, gotIt = true, now = 0)
            assertEquals(days * day, w.due)
            assertEquals(i + 1, w.reviews)
        }
        assertEquals(7, w.box)
        assertEquals(8, w.correct)
    }

    @Test fun againResetsToTenMinutes() {
        var w = Srs.review(Srs.review(word(), true, 0), true, 0)
        w = Srs.review(w, gotIt = false, now = 5_000)
        assertEquals(0, w.box)
        assertEquals(5_000 + 600_000L, w.due)
        assertEquals(3, w.reviews)
        assertEquals(2, w.correct)
    }

    @Test fun dueLabels() {
        assertEquals("due now", Srs.dueLabel(0, 10))
        assertEquals("in 3 days", Srs.dueLabel(3 * 86_400_000L, 0))
    }
}
