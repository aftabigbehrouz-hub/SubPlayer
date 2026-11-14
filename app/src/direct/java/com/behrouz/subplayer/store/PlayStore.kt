package com.behrouz.subplayer.store

import android.app.Activity
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/** Direct (APK) build: no Google Play. Access is handled by activation codes instead. */
class PlayStore(@Suppress("UNUSED_PARAMETER") ctx: Context) {
    enum class Status { CHECKING, ACTIVE, INACTIVE, PENDING, UNAVAILABLE }
    var status by mutableStateOf(Status.ACTIVE); private set
    var priceText by mutableStateOf<String?>(null); private set
    var trialDays by mutableStateOf(0); private set
    var error by mutableStateOf<String?>(null); private set
    val subscribed get() = false
    val trialLeft get() = 0
    val storeName = ""
    fun start() {}
    fun refresh() {}
    fun buy(@Suppress("UNUSED_PARAMETER") activity: Activity) {}
    fun manage(@Suppress("UNUSED_PARAMETER") activity: Activity) {}
    fun end() {}
}
