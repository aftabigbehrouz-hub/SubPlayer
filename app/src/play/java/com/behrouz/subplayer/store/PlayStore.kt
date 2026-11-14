package com.behrouz.subplayer.store

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClient.BillingResponseCode
import com.android.billingclient.api.BillingClient.ProductType
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams

/**
 * Google Play subscription: one yearly plan with a 10-day free trial for new customers.
 * Google Play shows the price, takes the payment, handles the trial, renewals and cancelling.
 */
class PlayStore(ctx: Context) {
    enum class Status { CHECKING, ACTIVE, INACTIVE, PENDING, UNAVAILABLE }

    private val app = ctx.applicationContext
    private val prefs = app.getSharedPreferences("play_store", Context.MODE_PRIVATE)

    var status by mutableStateOf(
        if (Entitlement.unlocked(Entitlement.Answer.NO_ANSWER, prefs.getLong("confirmed", 0), System.currentTimeMillis()))
            Status.ACTIVE else Status.CHECKING
    ); private set
    var priceText by mutableStateOf<String?>(null); private set     // e.g. "€29.99 / year"
    var trialDays by mutableStateOf(0); private set                  // > 0 when this user can still get the free trial
    var error by mutableStateOf<String?>(null); private set

    private var details: ProductDetails? = null
    private var offerToken: String? = null

    private val listener = PurchasesUpdatedListener { result, purchases ->
        when (result.responseCode) {
            BillingResponseCode.OK -> handle(purchases.orEmpty(), fromQuery = false)
            BillingResponseCode.USER_CANCELED -> error = null
            BillingResponseCode.ITEM_ALREADY_OWNED -> refresh()
            else -> error = describe(result)
        }
    }

    private val client: BillingClient = BillingClient.newBuilder(app)
        .setListener(listener)
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .enableAutoServiceReconnection()
        .build()

    fun start() {
        if (client.isReady) { refresh(); return }
        client.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(result: BillingResult) {
                if (result.responseCode == BillingResponseCode.OK) refresh() else noAnswer(describe(result))
            }
            override fun onBillingServiceDisconnected() { /* reconnects by itself */ }
        })
    }

    /** Ask Google Play again: is there an active subscription? what does it cost here? */
    fun refresh() {
        if (!client.isReady) { start(); return }
        client.queryPurchasesAsync(QueryPurchasesParams.newBuilder().setProductType(ProductType.SUBS).build()) { result, list ->
            if (result.responseCode == BillingResponseCode.OK) handle(list, fromQuery = true) else noAnswer(describe(result))
        }
        val params = QueryProductDetailsParams.newBuilder().setProductList(listOf(
            QueryProductDetailsParams.Product.newBuilder().setProductId(Entitlement.PRODUCT_ID).setProductType(ProductType.SUBS).build()
        )).build()
        client.queryProductDetailsAsync(params) { result, found ->
            if (result.responseCode != BillingResponseCode.OK) return@queryProductDetailsAsync
            val d = found.productDetailsList.firstOrNull() ?: run { error = "The subscription is not available in your country yet"; return@queryProductDetailsAsync }
            val offers = d.subscriptionOfferDetails.orEmpty().filter { it.basePlanId == Entitlement.BASE_PLAN_ID }
            // Play only lists the free trial to people who can still get it
            val trial = offers.firstOrNull { o -> o.pricingPhases.pricingPhaseList.any { it.priceAmountMicros == 0L } }
            val chosen = trial ?: offers.firstOrNull { it.offerId == null } ?: offers.firstOrNull()
            details = d
            offerToken = chosen?.offerToken
            val phases = chosen?.pricingPhases?.pricingPhaseList.orEmpty()
            val paid = phases.lastOrNull { it.priceAmountMicros > 0L }
            priceText = paid?.let { "${it.formattedPrice} / ${Entitlement.periodWord(it.billingPeriod)}" }
            trialDays = phases.firstOrNull { it.priceAmountMicros == 0L }?.let { Entitlement.days(it.billingPeriod) } ?: 0
        }
    }

    fun buy(activity: Activity) {
        val d = details
        val token = offerToken
        if (d == null || token == null) { error = "Google Play is not ready yet — check the internet connection and try again"; refresh(); return }
        val flow = BillingFlowParams.newBuilder().setProductDetailsParamsList(listOf(
            BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(d).setOfferToken(token).build()
        )).build()
        val r = client.launchBillingFlow(activity, flow)
        if (r.responseCode != BillingResponseCode.OK) error = describe(r)
    }

    /** Google Play's own page to cancel or change the subscription. */
    fun manage(activity: Activity) {
        val url = "https://play.google.com/store/account/subscriptions?sku=${Entitlement.PRODUCT_ID}&package=${app.packageName}"
        runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
    }

    fun end() { runCatching { client.endConnection() } }

    private fun handle(purchases: List<Purchase>, fromQuery: Boolean) {
        val mine = purchases.filter { Entitlement.PRODUCT_ID in it.products }
        val bought = mine.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }
        bought.filter { !it.isAcknowledged }.forEach { p ->
            // must be acknowledged within 3 days, or Google refunds it automatically
            client.acknowledgePurchase(AcknowledgePurchaseParams.newBuilder().setPurchaseToken(p.purchaseToken).build()) { }
        }
        when {
            bought.isNotEmpty() -> {
                prefs.edit().putLong("confirmed", System.currentTimeMillis()).apply()
                error = null
                status = Status.ACTIVE
            }
            mine.any { it.purchaseState == Purchase.PurchaseState.PENDING } -> status = Status.PENDING
            fromQuery -> {
                prefs.edit().remove("confirmed").apply()
                status = Status.INACTIVE
            }
        }
    }

    private fun noAnswer(why: String) {
        val ok = Entitlement.unlocked(Entitlement.Answer.NO_ANSWER, prefs.getLong("confirmed", 0), System.currentTimeMillis())
        status = if (ok) Status.ACTIVE else Status.UNAVAILABLE
        if (!ok) error = why
    }

    private fun describe(r: BillingResult): String = when (r.responseCode) {
        BillingResponseCode.SERVICE_UNAVAILABLE, BillingResponseCode.SERVICE_DISCONNECTED, BillingResponseCode.NETWORK_ERROR ->
            "No connection to Google Play — check the internet connection"
        BillingResponseCode.BILLING_UNAVAILABLE -> "Google Play billing is not available on this phone or account"
        BillingResponseCode.ITEM_UNAVAILABLE -> "The subscription is not available in your country yet"
        BillingResponseCode.DEVELOPER_ERROR -> "Install SubPlayer from Google Play to subscribe"
        else -> "Google Play: " + (r.debugMessage.ifBlank { "error ${r.responseCode}" })
    }
}
