package com.behrouz.subplayer.store

/**
 * Pure rules for the Google Play subscription (kept here so they are unit-tested).
 *
 * The app asks Google Play on every start and every return to the app. If Play cannot
 * answer (no internet, Play Store being updated), a subscriber keeps access for
 * [GRACE_MS] after the last time Play confirmed the subscription.
 */
object Entitlement {
    const val PRODUCT_ID = "subplayer_pro"          // Play Console › Monetize › Subscriptions
    const val BASE_PLAN_ID = "yearly"               // auto-renewing, every 1 year
    const val TRIAL_OFFER_ID = "free-trial-10d"     // free trial, 10 days, new customers only
    const val GRACE_MS = 3L * 24 * 60 * 60 * 1000

    enum class Answer { ACTIVE, INACTIVE, NO_ANSWER }

    fun unlocked(answer: Answer, lastConfirmedActive: Long, now: Long): Boolean = when (answer) {
        Answer.ACTIVE -> true
        Answer.INACTIVE -> false
        Answer.NO_ANSWER -> lastConfirmedActive > 0 && now >= lastConfirmedActive && now - lastConfirmedActive <= GRACE_MS
    }

    /** ISO-8601 period from Play ("P10D", "P1W", "P1M", "P1Y") → days; 0 if unknown. */
    fun days(period: String): Int {
        val m = Regex("""^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?$""").find(period.trim()) ?: return 0
        val (y, mo, w, d) = m.destructured
        return (y.toIntOrNull() ?: 0) * 365 + (mo.toIntOrNull() ?: 0) * 30 + (w.toIntOrNull() ?: 0) * 7 + (d.toIntOrNull() ?: 0)
    }

    /** "P1Y" → "year", "P1M" → "month", "P3M" → "3 months" … for the price line. */
    fun periodWord(period: String): String = when (period.trim()) {
        "P1Y" -> "year"; "P1M" -> "month"; "P1W" -> "week"
        else -> days(period).let { if (it % 30 == 0 && it >= 60) "${it / 30} months" else "$it days" }
    }
}
