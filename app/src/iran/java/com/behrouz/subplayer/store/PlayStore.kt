package com.behrouz.subplayer.store

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.behrouz.subplayer.BuildConfig
import com.behrouz.subplayer.licence.Licence
import ir.myket.billingclient.IabHelper
import ir.myket.billingclient.util.IabResult
import ir.myket.billingclient.util.Inventory
import ir.myket.billingclient.util.Purchase

/**
 * Cafe Bazaar and Myket builds. Both stores speak the same in-app billing protocol; Myket's official
 * library (ir.myket.billingclient) talks to whichever store this build was made for (see build.gradle.kts).
 *
 * 10-day free trial: run by the app on the phone, as in the direct APK. After that a yearly subscription
 * bought through the store unlocks SubPlayer.
 */
class PlayStore(ctx: Context) {
    enum class Status { CHECKING, ACTIVE, INACTIVE, PENDING, UNAVAILABLE }

    private val app = ctx.applicationContext
    private val prefs = app.getSharedPreferences("store_sub", Context.MODE_PRIVATE)
    private val helper: IabHelper? = BuildConfig.IAB_PUBLIC_KEY.takeIf { it.isNotBlank() }?.let { IabHelper(app, it) }
    private var ready = false

    val storeName = if (BuildConfig.STORE == "myket") "مایکت" else "کافه‌بازار"
    var subscribed by mutableStateOf(
        Entitlement.unlocked(Entitlement.Answer.NO_ANSWER, prefs.getLong("confirmed", 0), System.currentTimeMillis())
    ); private set
    var trialLeft by mutableIntStateOf(Licence.checkTrial(app)); private set
    var status by mutableStateOf(if (subscribed || trialLeft > 0) Status.ACTIVE else Status.CHECKING); private set
    var priceText by mutableStateOf<String?>(null); private set
    val trialDays get() = 0                  // the trial is the app's own, not the store's
    var error by mutableStateOf<String?>(null); private set

    private fun update() {
        status = if (subscribed || trialLeft > 0) Status.ACTIVE else if (status == Status.UNAVAILABLE) Status.UNAVAILABLE else Status.INACTIVE
    }

    fun start() {
        trialLeft = Licence.checkTrial(app)
        val h = helper ?: run { error = "$storeName payment is not set up in this build yet (public key missing)"; update(); return }
        if (ready) { refresh(); return }
        runCatching {
            h.startSetup { result: IabResult ->
                if (result.isSuccess) { ready = true; refresh() } else noAnswer(installHint())
            }
        }.onFailure { noAnswer(installHint()) }
    }

    /** Ask the store: does this user have an active subscription? What does it cost? */
    fun refresh() {
        trialLeft = Licence.checkTrial(app)
        update()
        val h = helper ?: return
        if (!ready) { start(); return }
        runCatching {
            h.queryInventoryAsync(true, listOf(Entitlement.PRODUCT_ID)) { result: IabResult, inv: Inventory? ->
                if (!result.isSuccess || inv == null) { noAnswer(result.message ?: "No answer from $storeName"); return@queryInventoryAsync }
                inv.getSkuDetails(Entitlement.PRODUCT_ID)?.price?.let { priceText = "$it / سال (year)" }
                val p: Purchase? = inv.getPurchase(Entitlement.PRODUCT_ID)
                if (p != null && p.purchaseState == 0) confirm() else {
                    prefs.edit().remove("confirmed").apply()
                    subscribed = false
                }
                update()
            }
        }   // another query still running: the next refresh catches up
    }

    fun buy(activity: Activity) {
        val h = helper ?: run { error = "$storeName payment is not set up in this build yet"; return }
        runCatching {
            h.launchSubscriptionPurchaseFlow(activity, Entitlement.PRODUCT_ID) { result: IabResult, p: Purchase? ->
                when {
                    result.isSuccess && p != null -> { confirm(); update() }
                    result.response == IabHelper.IABHELPER_USER_CANCELLED || result.response == IabHelper.BILLING_RESPONSE_RESULT_USER_CANCELED -> error = null
                    else -> error = result.message ?: "Payment failed"
                }
            }
        }.onFailure { error = "Please wait a moment and try again" }
    }

    /** The app's page in the store (subscriptions are managed in the store app). */
    fun manage(activity: Activity) {
        val pkg = app.packageName
        val uri = if (BuildConfig.STORE == "myket") "myket://details?id=$pkg" else "bazaar://details?id=$pkg"
        val web = if (BuildConfig.STORE == "myket") "https://myket.ir/app/$pkg" else "https://cafebazaar.ir/app/$pkg"
        runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(uri))) }
            .onFailure { runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(web))) } }
    }

    fun end() { runCatching { helper?.dispose() } }

    private fun confirm() {
        prefs.edit().putLong("confirmed", System.currentTimeMillis()).apply()
        subscribed = true
        error = null
    }

    private fun noAnswer(why: String) {
        subscribed = Entitlement.unlocked(Entitlement.Answer.NO_ANSWER, prefs.getLong("confirmed", 0), System.currentTimeMillis())
        if (!subscribed && trialLeft <= 0) { status = Status.UNAVAILABLE; error = why } else update()
    }

    private fun installHint() =
        if (BuildConfig.STORE == "myket") "Myket is needed to subscribe — install Myket (myket.ir) and try again"
        else "Cafe Bazaar is needed to subscribe — install Bazaar (cafebazaar.ir) and try again"
}
