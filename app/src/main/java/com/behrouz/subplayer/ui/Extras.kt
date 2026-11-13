package com.behrouz.subplayer.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.media3.common.util.UnstableApi
import com.behrouz.subplayer.AppViewModel
import kotlinx.coroutines.launch

private val W = Color.White

// ============================================================ help guide

private data class HelpItem(val icon: ImageVector, val title: String, val text: String)

private val HELP = listOf(
    HelpItem(Icons.Folder, "Open a video",
        "Folder icon (top bar, or in full screen). The clock icon lists recent videos and continues where you stopped. " +
            "You can also choose “Open with ▸ SubPlayer” in your file manager."),
    HelpItem(Icons.Subtitles, "Make subtitles",
        "Subtitles ▸ choose the spoken language and quality ▸ Start. Everything runs on your phone, offline. " +
            "Fast = quick, no punctuation. Accurate (Whisper Base) = recommended. Best (Whisper Small) = most accurate, " +
            "takes about as long as the video. Each model downloads once. Subtitles are saved and reload next time. " +
            "Already have subtitles? “Load .srt”."),
    HelpItem(Icons.Star, "Tap a word",
        "Pause (tap the picture) and tap any word in the subtitle: article, IPA, meanings with examples, English, " +
            "Persian, the phone's voice (also slow), a real recording when online, and DWDS. " +
            "Inflected words find their base form (ging → gehen). The dictionary (38 MB) downloads with your first tap."),
    HelpItem(Icons.Copy, "Phrases & whole lines",
        "Long-press the first word, then tap the last word: the phrase is translated into English and Persian " +
            "(needs internet) and each word's meaning is listed (offline). Double-tap a word to translate the whole line."),
    HelpItem(Icons.School, "Save & review",
        "In any word or phrase card tap ★ Save. The meaning, the sentence and the exact video moment are kept. " +
            "Saved words glow gold in subtitles. My Words (★ top bar) shows how many times you reviewed each word and " +
            "when it is due. Review plays the moment in the video, then you answer: “Got it” = next review later " +
            "(1, 2, 4, 7, 15, 30, 60 days), “Again” = back in 10 minutes. Turn on the daily reminder to be notified."),
    HelpItem(Icons.Repeat, "Repeat like VLC",
        "A = start of the loop, B = end; it repeats until you press ✕. “Loop line” repeats the current subtitle. " +
            "⏮ ⏭ jump to the previous / next line; 1× ▸ 0.75× ▸ 0.5× slows the speech without changing the voice pitch."),
    HelpItem(Icons.Download, "Save a clip",
        "After setting A and B, “Save clip” writes that part as a new video to Movies/SubPlayer — " +
            "tick “Burn subtitles” to draw the subtitles into the picture. Good for sharing or flashcards."),
    HelpItem(Icons.Fullscreen, "Full screen",
        "Full screen (or just turn the phone sideways). Tap once to show/hide the controls, double-tap the left or right " +
            "side to jump 5 seconds, double-tap the middle to play/pause. Subtitle words stay tappable. Back exits."),
    HelpItem(Icons.Lock, "Offline & privacy",
        "Subtitles, dictionary, review and clip saving work without internet. Only sentence translation, real recordings " +
            "and DWDS go online. Your videos never leave your phone.")
)

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HelpSheet(vm: AppViewModel) {
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = SheetBg) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 24.dp)) {
            NeonTitle("How SubPlayer works", 24.sp)
            Explain("Everything in one place. You can replay the intro tour at the bottom.", Modifier.padding(bottom = 12.dp))
            HELP.forEach { h ->
                Row(Modifier.fillMaxWidth().padding(vertical = 5.dp).glass(RoundedCornerShape(20.dp)).padding(14.dp)) {
                    Box(Modifier.size(38.dp).background(Neon.brush, CircleShape), contentAlignment = Alignment.Center) {
                        Icon(h.icon, null, tint = Color(0xFF0B0A1A), modifier = Modifier.size(20.dp))
                    }
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text(h.title, color = W, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        Explain(h.text, Modifier.padding(top = 3.dp))
                    }
                }
            }
            TextButton(onClick = { vm.sheet = null; vm.showTour = true }) { Text("Replay the intro tour", color = Neon.Cyan) }
        }
    }
}

// ============================================================ first-run tour

private data class TourPage(val icon: ImageVector, val title: String, val text: String)

private val TOUR = listOf(
    TourPage(Icons.Play, "Welcome to SubPlayer", "Turn any video into a German lesson — subtitles, meanings and memory, all on your phone."),
    TourPage(Icons.Subtitles, "Subtitles, made for you", "Open a video and tap Subtitles. Whisper listens and writes what is said — offline."),
    TourPage(Icons.Star, "Tap any word", "Pause and tap a word: meaning in English and Persian, IPA, examples, pronunciation. Long-press for phrases."),
    TourPage(Icons.School, "Remember it", "★ Save words. They come back for review right before you'd forget, with the video moment they came from."),
    TourPage(Icons.Repeat, "Loop the hard parts", "A–B or Loop line repeats a sentence until you hear every sound. Slow it down to 0.5×.")
)

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun Tour(vm: AppViewModel) {
    val pager = rememberPagerState { TOUR.size }
    val scope = rememberCoroutineScope()
    Dialog(onDismissRequest = { vm.finishTour() }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(Modifier.fillMaxSize()) {
            Aurora(Modifier.fillMaxSize())
            Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(24.dp)) {
                Row { Spacer(Modifier.weight(1f)); TextButton(onClick = { vm.finishTour() }) { Text("Skip", color = W.copy(alpha = 0.7f)) } }
                HorizontalPager(pager, Modifier.weight(1f)) { i ->
                    val p = TOUR[i]
                    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        Box(
                            Modifier.size(130.dp).background(Neon.hot, CircleShape),
                            contentAlignment = Alignment.Center
                        ) { Icon(p.icon, null, tint = Color(0xFF0B0A1A), modifier = Modifier.size(64.dp)) }
                        Spacer(Modifier.height(36.dp))
                        NeonTitle(p.title, 28.sp)
                        Spacer(Modifier.height(12.dp))
                        Text(p.text, color = W.copy(alpha = 0.8f), fontSize = 17.sp, textAlign = TextAlign.Center, lineHeight = 25.sp)
                    }
                }
                Row(Modifier.fillMaxWidth().padding(vertical = 16.dp), horizontalArrangement = Arrangement.Center) {
                    repeat(TOUR.size) { i ->
                        Box(Modifier.padding(4.dp).size(if (i == pager.currentPage) 22.dp else 8.dp, 8.dp)
                            .background(if (i == pager.currentPage) Neon.Cyan else W.copy(alpha = 0.3f), RoundedCornerShape(4.dp)))
                    }
                }
                val last = pager.currentPage == TOUR.size - 1
                GlowButton(if (last) "Let's start" else "Next", Modifier.fillMaxWidth()) {
                    if (last) vm.finishTour() else scope.launch { pager.animateScrollToPage(pager.currentPage + 1) }
                }
            }
        }
    }
}

// ============================================================ recent videos

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VideosSheet(vm: AppViewModel, onOpenVideo: () -> Unit) {
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, containerColor = SheetBg) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 24.dp)) {
            NeonTitle("Videos", 24.sp)
            Explain("Recently opened videos continue where you stopped.", Modifier.padding(bottom = 12.dp))
            GlowButton("Open another video", Modifier.fillMaxWidth(), icon = Icons.Folder) { vm.sheet = null; onOpenVideo() }
            Spacer(Modifier.height(12.dp))
            if (vm.recentList.isEmpty()) Explain("No recent videos yet.")
            vm.recentList.forEach { RecentRow(vm, it) }
        }
    }
}

// ============================================================ settings

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsSheet(vm: AppViewModel) {
    val ctx = LocalContext.current
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = SheetBg) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().imePadding().padding(bottom = 24.dp)) {
            NeonTitle("Settings", 24.sp)
            Spacer(Modifier.height(10.dp))

            Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(20.dp)).padding(16.dp)) {
                Text("Licence", color = W, fontWeight = FontWeight.Bold)
                if (vm.licence != null) {
                    Explain("Licensed to ${vm.licence?.name} · device code ${vm.deviceCode}", Modifier.padding(top = 4.dp))
                } else {
                    Explain("Free trial · ${vm.trialLeft} of ${com.behrouz.subplayer.licence.Licence.TRIAL_DAYS} days left · device code ${vm.deviceCode}",
                        Modifier.padding(top = 4.dp, bottom = 10.dp))
                    GlowButton("Buy / activate", Modifier.fillMaxWidth()) { vm.sheet = null; vm.showActivation = true }
                }
            }

            if (vm.isOwner) {
                Spacer(Modifier.height(12.dp))
                OwnerTools(vm, ctx)
            }

            Spacer(Modifier.height(12.dp))
            Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(20.dp)).padding(16.dp)) {
                Text("About", color = W, fontWeight = FontWeight.Bold)
                Explain("SubPlayer · speech recognition: Whisper (OpenAI, via whisper.cpp) and Vosk · dictionary: Wiktionary " +
                    "(CC BY-SA 4.0) · sentence translation: Google Translate / MyMemory (online only).", Modifier.padding(top = 4.dp))
                TextButton(onClick = { vm.sheet = null; vm.showTour = true }) { Text("Replay the intro tour", color = Neon.Cyan) }
            }
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun OwnerTools(vm: AppViewModel, ctx: Context) {
    var device by remember { mutableStateOf("") }
    var buyer by remember { mutableStateOf("") }
    var code by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(20.dp)).padding(16.dp)) {
        Text("Owner tools · create an activation code", color = Neon.Gold, fontWeight = FontWeight.Bold)
        Explain("The buyer opens SubPlayer and sends you the device code shown on the activation screen. " +
            "Enter it with their name; the code you create works only on that phone.", Modifier.padding(vertical = 6.dp))
        GlassField(device, { device = it.uppercase() }, "Buyer's device code (XXXXX-XXXXX)")
        Spacer(Modifier.height(8.dp))
        GlassField(buyer, { buyer = it }, "Buyer's name")
        Spacer(Modifier.height(10.dp))
        GlowButton("Create code", Modifier.fillMaxWidth()) { code = vm.createActivationCode(device, buyer) }
        code?.let { c ->
            Spacer(Modifier.height(10.dp))
            SelectionContainer { Text(c, color = W, fontFamily = FontFamily.Monospace, fontSize = 12.sp) }
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("Copy", icon = Icons.Copy) { copy(ctx, c); vm.message = "Activation code copied" }
                Pill("Share", icon = Icons.Share) { share(ctx, "SubPlayer activation code for ${buyer.trim()}:\n\n$c") }
            }
        }
        TextButton(onClick = { vm.forgetOwnerKey() }) { Text("Remove owner key from this phone", color = Neon.Pink) }
    }
}

// ============================================================ activation (lock) screen

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
fun LockScreen(vm: AppViewModel) {
    val ctx = LocalContext.current
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var ownerMode by remember { mutableStateOf(false) }
    var key by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    BackHandler(enabled = !vm.trialEnded) { vm.showActivation = false }
    Box(Modifier.fillMaxSize()) {
        Aurora(Modifier.fillMaxSize())
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).statusBarsPadding().navigationBarsPadding().imePadding().padding(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            val ended = vm.trialEnded
            val tg = "@" + com.behrouz.subplayer.licence.Licence.SELLER_TELEGRAM
            if (!ended) {
                Row(Modifier.fillMaxWidth()) {
                    TextButton(onClick = { vm.showActivation = false }) { Text("‹ Back to the app", color = W.copy(alpha = 0.7f)) }
                }
            } else Spacer(Modifier.height(30.dp))
            Box(Modifier.size(96.dp).background(Neon.hot, CircleShape), contentAlignment = Alignment.Center) {
                Icon(Icons.Lock, null, tint = Color(0xFF0B0A1A), modifier = Modifier.size(46.dp))
            }
            Spacer(Modifier.height(20.dp))
            NeonTitle(if (ended) "Your free trial has ended" else "Buy SubPlayer", 28.sp)
            Text(
                if (ended) "Thank you for trying SubPlayer for ${com.behrouz.subplayer.licence.Licence.TRIAL_DAYS} days! " +
                    "To keep using it, send your device code to $tg on Telegram. You'll receive an activation code for this phone."
                else "${vm.trialLeft} day${if (vm.trialLeft == 1) "" else "s"} of your free trial left. To buy, send your device code " +
                    "to $tg on Telegram; you'll receive an activation code for this phone.",
                color = W.copy(alpha = 0.85f), fontSize = 16.sp, textAlign = TextAlign.Center, lineHeight = 23.sp,
                modifier = Modifier.padding(top = 10.dp, bottom = 16.dp)
            )
            GlowButton("Message $tg on Telegram", Modifier.fillMaxWidth(), icon = Icons.Share) { vm.contactSeller() }
            Explain("Opens Telegram and copies your device code — just paste it in the chat.",
                Modifier.padding(top = 8.dp, bottom = 18.dp))

            Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(24.dp)).padding(18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("YOUR DEVICE CODE", color = Neon.Cyan, fontSize = 12.sp, letterSpacing = 1.5.sp, fontWeight = FontWeight.Bold)
                Text(vm.deviceCode, color = W, fontSize = 30.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(vertical = 8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Pill("Copy", icon = Icons.Copy) { copy(ctx, vm.deviceCode); android.widget.Toast.makeText(ctx, "Device code copied", android.widget.Toast.LENGTH_SHORT).show() }
                    Pill("Send", icon = Icons.Share) { share(ctx, "My SubPlayer device code: ${vm.deviceCode}") }
                }
            }
            Spacer(Modifier.height(16.dp))
            Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(24.dp)).padding(18.dp)) {
                Text("Got your activation code?", color = W, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                GlassField(code, { code = it; error = null }, "Paste the code you received", singleLine = false)
                error?.let { Text(it, color = Neon.Pink, fontSize = 13.sp, modifier = Modifier.padding(top = 6.dp)) }
                Spacer(Modifier.height(12.dp))
                GlowButton("Activate", Modifier.fillMaxWidth(), icon = Icons.Check) {
                    if (!vm.activate(code)) error = "This code is not valid for this phone. Check that the whole code was pasted."
                }
            }
            Spacer(Modifier.height(16.dp))
            if (!ownerMode) {
                TextButton(onClick = { ownerMode = true }) { Text("I'm the owner", color = W.copy(alpha = 0.6f)) }
            } else {
                Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(24.dp)).padding(18.dp)) {
                    Text("Owner unlock", color = Neon.Gold, fontWeight = FontWeight.Bold)
                    Explain("Paste the contents of SUBPLAYER_LICENCE_PRIVATE_KEY.txt. It is checked against the key built into the app, " +
                        "stored only on this phone, and unlocks the tool that creates codes for buyers.", Modifier.padding(vertical = 6.dp))
                    GlassField(name, { name = it }, "Your name")
                    Spacer(Modifier.height(8.dp))
                    GlassField(key, { key = it; error = null }, "Private key", singleLine = false)
                    Spacer(Modifier.height(12.dp))
                    GlowButton("Unlock as owner", Modifier.fillMaxWidth()) {
                        if (!vm.becomeOwner(key, name)) error = "That is not the owner key for this app."
                    }
                }
            }
        }
    }
}

@Composable
fun GlassField(value: String, onChange: (String) -> Unit, label: String, singleLine: Boolean = true) {
    OutlinedTextField(
        value = value, onValueChange = onChange, label = { Text(label) }, singleLine = singleLine,
        maxLines = if (singleLine) 1 else 5,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = W, unfocusedTextColor = W,
            focusedBorderColor = Neon.Cyan, unfocusedBorderColor = W.copy(alpha = 0.25f),
            focusedLabelColor = Neon.Cyan, unfocusedLabelColor = W.copy(alpha = 0.6f), cursorColor = Neon.Cyan
        )
    )
}

private fun copy(ctx: Context, text: String) {
    val cm = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("SubPlayer", text))
}

private fun share(ctx: Context, text: String) {
    val i = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    ctx.startActivity(Intent.createChooser(i, "Send").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}
