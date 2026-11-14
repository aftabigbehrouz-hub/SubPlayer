package com.behrouz.subplayer

import com.behrouz.subplayer.store.Entitlement
import com.behrouz.subplayer.store.Entitlement.Answer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EntitlementTest {
    private val now = 1_800_000_000_000L
    private val day = 24L * 60 * 60 * 1000

    @Test fun playAnswerDecides() {
        assertTrue(Entitlement.unlocked(Answer.ACTIVE, 0, now))
        assertFalse(Entitlement.unlocked(Answer.INACTIVE, now - 1000, now))   // cancelled/expired: locked even if seen recently
    }

    @Test fun offlineGraceThreeDays() {
        assertTrue(Entitlement.unlocked(Answer.NO_ANSWER, now - 2 * day, now))
        assertTrue(Entitlement.unlocked(Answer.NO_ANSWER, now - 3 * day, now))
        assertFalse(Entitlement.unlocked(Answer.NO_ANSWER, now - 3 * day - 1, now))
        assertFalse(Entitlement.unlocked(Answer.NO_ANSWER, 0, now))              // never confirmed
        assertFalse(Entitlement.unlocked(Answer.NO_ANSWER, now + day, now))      // clock turned back
    }

    @Test fun periods() {
        assertEquals(10, Entitlement.days("P10D"))
        assertEquals(14, Entitlement.days("P2W"))
        assertEquals(365, Entitlement.days("P1Y"))
        assertEquals(0, Entitlement.days("garbage"))
        assertEquals("year", Entitlement.periodWord("P1Y"))
        assertEquals("month", Entitlement.periodWord("P1M"))
        assertEquals("3 months", Entitlement.periodWord("P3M"))
    }
}
