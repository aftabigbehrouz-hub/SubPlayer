package com.behrouz.subplayer.ui

import android.app.Activity
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.store.PlayStore

const val PRIVACY_URL = "https://github.com/aftabigbehrouz-hub/SubPlayer/blob/main/PRIVACY.md"
const val TERMS_URL = "https://github.com/aftabigbehrouz-hub/SubPlayer/blob/main/TERMS.md"

private val W = Color.White

private val FEATURES = listOf(
    "Subtitles for your own German and English videos — offline on your phone",
    "Tap any word: meaning, IPA, examples, English · German · Persian",
    "Loop any part like VLC (A-B), pause after each line, shadowing",
    "Save words with the exact video moment, review at the right time",
    "Gap-fill, dictation and der·die·das practice",
    "Sync your words with the Windows app"
)

/** Google Play build: shown until Google Play confirms an active subscription (or free trial). */
@Composable
fun Paywall(vm: AppViewModel, activity: Activity) {
    val s = vm.playStore
    val ctx = LocalContext.current
    fun open(url: String) = runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
    Box(Modifier.fillMaxSize()) {
        Aurora(Modifier.fillMaxSize())
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding().navigationBarsPadding().padding(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(Modifier.height(24.dp))
            Box(Modifier.size(88.dp).background(Neon.hot, CircleShape), contentAlignment = Alignment.Center) {
                Icon(Icons.Subtitles, null, tint = Color(0xFF0B0A1A), modifier = Modifier.size(44.dp))
            }
            Spacer(Modifier.height(18.dp))
            NeonTitle("SubPlayer", 32.sp)
            Text("Learn German and English with your own videos", color = W.copy(alpha = 0.85f), fontSize = 16.sp,
                textAlign = TextAlign.Center, modifier = Modifier.padding(top = 6.dp, bottom = 18.dp))

            Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(24.dp)).padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)) {
                FEATURES.forEach { f ->
                    Row(verticalAlignment = Alignment.Top) {
                        Text("✓", color = Neon.Cyan, fontWeight = FontWeight.Bold, modifier = Modifier.padding(end = 10.dp))
                        Text(f, color = W, fontSize = 15.sp, lineHeight = 20.sp)
                    }
                }
            }
            Spacer(Modifier.height(20.dp))

            when (s.status) {
                PlayStore.Status.CHECKING -> {
                    CircularProgressIndicator(color = Neon.Cyan)
                    Explain("Checking your subscription with Google Play…", Modifier.padding(top = 10.dp))
                }
                PlayStore.Status.PENDING -> {
                    Text("Your payment is being processed", color = Neon.Gold, fontWeight = FontWeight.Bold)
                    Explain("SubPlayer opens as soon as Google Play confirms it.", Modifier.padding(top = 6.dp))
                    TextButton(onClick = { s.refresh() }) { Text("Check again", color = Neon.Cyan) }
                }
                else -> {
                    val price = s.priceText
                    val title = if (s.trialDays > 0) "Start ${s.trialDays}-day free trial" else "Subscribe"
                    GlowButton(title, Modifier.fillMaxWidth(), icon = Icons.Check, enabled = price != null) { s.buy(activity) }
                    Text(
                        when {
                            price == null -> "Loading the price from Google Play…"
                            s.trialDays > 0 -> "Free for ${s.trialDays} days, then $price. Renews every year until you cancel. " +
                                "Cancel at least a day before the trial ends and you pay nothing."
                            else -> "$price. Renews every year until you cancel."
                        },
                        color = W.copy(alpha = 0.85f), fontSize = 14.sp, textAlign = TextAlign.Center, lineHeight = 19.sp,
                        modifier = Modifier.padding(top = 10.dp)
                    )
                    s.error?.let { Text(it, color = Neon.Pink, fontSize = 13.sp, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 8.dp)) }
                    Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        TextButton(onClick = { s.refresh() }) { Text("Restore purchase", color = Neon.Cyan) }
                        TextButton(onClick = { s.manage(activity) }) { Text("Manage in Google Play", color = Neon.Cyan) }
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            Explain("Payment is charged to your Google account. Cancel any time in Google Play ▸ Payments & subscriptions; " +
                "you keep access until the end of the paid year.", Modifier.padding(horizontal = 8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = { open(PRIVACY_URL) }) { Text("Privacy policy", color = W.copy(alpha = 0.6f), fontSize = 13.sp) }
                TextButton(onClick = { open(TERMS_URL) }) { Text("Terms of use", color = W.copy(alpha = 0.6f), fontSize = 13.sp) }
            }
        }
    }
}

/** Settings card in the Google Play build. */
@Composable
fun SubscriptionCard(vm: AppViewModel) {
    val s = vm.playStore
    val activity = LocalContext.current as? Activity
    Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(20.dp)).padding(16.dp)) {
        Text("Subscription", color = W, fontWeight = FontWeight.Bold)
        Explain(
            when (s.status) {
                PlayStore.Status.ACTIVE -> "Active — thank you! Google Play renews it every year until you cancel."
                PlayStore.Status.PENDING -> "Payment being processed by Google Play."
                else -> "Not active."
            },
            Modifier.padding(top = 4.dp, bottom = 6.dp)
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Pill("Manage / cancel") { activity?.let { s.manage(it) } }
            Pill("Privacy policy") { activity?.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(PRIVACY_URL))) }
        }
    }
}
