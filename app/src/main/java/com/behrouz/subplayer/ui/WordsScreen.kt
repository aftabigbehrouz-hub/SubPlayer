package com.behrouz.subplayer.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.Screen
import com.behrouz.subplayer.words.SavedWord
import com.behrouz.subplayer.words.Srs

private val W = Color.White

// ============================================================ word list

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
fun WordsScreen(vm: AppViewModel) {
    BackHandler { vm.screen = Screen.PLAYER }
    val now = System.currentTimeMillis()
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 32.dp)
    ) {
        item {
            Row(Modifier.fillMaxWidth().statusBarsPadding().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { vm.screen = Screen.PLAYER }) { Icon(Icons.Back, "Back", tint = W) }
                NeonTitle("My Words", 26.sp, Modifier.weight(1f))
            }
            Explain(
                "Every word or phrase you save keeps its meaning, its sentence and the exact moment in the video. " +
                    "Review brings each one back just before you'd forget it: “Got it” waits longer next time " +
                    "(1 → 2 → 4 → 7 → 15 → 30 → 60 days), “Again” brings it back in 10 minutes.",
                Modifier.padding(start = 12.dp, end = 4.dp, bottom = 14.dp)
            )
            // stats
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Stat("Saved", vm.words.size.toString(), Modifier.weight(1f))
                Stat("Due now", vm.dueCount.toString(), Modifier.weight(1f), Neon.Pink)
                Stat("Reviews", vm.words.sumOf { it.reviews }.toString(), Modifier.weight(1f), Neon.Cyan)
                Stat("Mastered", vm.words.count { it.box >= 5 }.toString(), Modifier.weight(1f), Neon.Gold)
            }
            Spacer(Modifier.height(14.dp))
            GlowButton(
                if (vm.dueCount > 0) "Review ${vm.dueCount} due now" else "Practise anyway",
                Modifier.fillMaxWidth(), icon = Icons.School, enabled = vm.words.isNotEmpty()
            ) { vm.startReview() }
            Spacer(Modifier.height(12.dp))
            ReminderCard(vm)
            Spacer(Modifier.height(10.dp))
            if (vm.words.isEmpty()) {
                Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.StarOutline, null, tint = Neon.Gold, modifier = Modifier.size(40.dp))
                    Spacer(Modifier.height(8.dp))
                    Text("No words yet", color = W, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
                    Explain("While watching: pause → tap a word (or long-press for a phrase) → tap ★ Save. " +
                        "Saved words glow gold in the subtitles.", Modifier.padding(top = 6.dp))
                }
            }
        }
        items(vm.words, key = { it.id }) { w -> WordCard(vm, w, now) }
    }
}

@Composable
private fun Stat(label: String, value: String, modifier: Modifier, color: Color = W) {
    Column(modifier.glass(RoundedCornerShape(18.dp)).padding(vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, color = color, fontSize = 22.sp, fontWeight = FontWeight.Black)
        Text(label, color = W.copy(alpha = 0.6f), fontSize = 11.sp)
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun ReminderCard(vm: AppViewModel) {
    Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(20.dp)).padding(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Bell, null, tint = if (vm.reminderOn) Neon.Cyan else W.copy(alpha = 0.5f))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text("Daily reminder", color = W, fontWeight = FontWeight.SemiBold)
                Explain(if (vm.reminderOn) "A notification at %02d:00 when words are due".format(vm.reminderHour)
                    else "Get a notification when words are waiting")
            }
            Pill(if (vm.reminderOn) "On" else "Off", active = vm.reminderOn) { vm.requestReminder(!vm.reminderOn, vm.reminderHour) }
        }
        if (vm.reminderOn) {
            Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(8, 13, 18, 21).forEach { h ->
                    Pill("%02d:00".format(h), active = vm.reminderHour == h) { vm.requestReminder(true, h) }
                }
            }
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun WordCard(vm: AppViewModel, w: SavedWord, now: Long) {
    var open by remember { mutableStateOf(false) }
    Column(
        Modifier.fillMaxWidth().padding(vertical = 5.dp).glass(RoundedCornerShape(22.dp))
            .clickable { open = !open }.padding(16.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            StrengthRing(Srs.strength(w))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.Bottom) {
                    if (w.article.isNotEmpty()) Text(w.article + " ", color = articleTint(w.article), fontSize = 16.sp)
                    Text(if (w.lemma.isNotEmpty() && w.lemma != w.text && !w.text.contains(' ')) w.lemma else w.text,
                        color = W, fontSize = 19.sp, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                val meaning = listOf(w.english, w.persian).filter { it.isNotBlank() }.joinToString("  ·  ")
                if (meaning.isNotEmpty()) Text(meaning, color = W.copy(alpha = 0.75f), fontSize = 13.sp, maxLines = if (open) 6 else 1, overflow = TextOverflow.Ellipsis)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("${w.reviews}×", color = Neon.Cyan, fontWeight = FontWeight.Bold)
                Text(Srs.dueLabel(w.due, now), color = if (w.due <= now) Neon.Pink else W.copy(alpha = 0.55f), fontSize = 11.sp)
            }
        }
        AnimatedVisibility(open, enter = expandVertically() + fadeIn()) {
            Column(Modifier.padding(top = 12.dp)) {
                if (w.ipa.isNotEmpty()) Text(w.ipa, color = W.copy(alpha = 0.7f), fontSize = 15.sp)
                Text(highlight(w.sentence, w.text), color = W.copy(alpha = 0.9f), fontStyle = FontStyle.Italic,
                    modifier = Modifier.padding(vertical = 8.dp))
                Explain("From “${w.videoName}” at ${fmt(w.startMs)} · reviewed ${w.reviews}× (${w.correct} correct)" +
                    if (w.lastReview > 0) " · last ${Srs.dueLabel(w.lastReview, now).replace("in ", "")} ago".replace("due now ago", "just now") else "")
                Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Pill("Play in video", icon = Icons.Play) { vm.playClip(w, stayOnScreen = false) }
                    Pill("Speak", icon = Icons.Volume) { vm.speak(if (w.text.contains(' ')) w.text else w.lemma.ifEmpty { w.text }) }
                    Spacer(Modifier.weight(1f))
                    IconButton(onClick = { vm.deleteWord(w) }) { Icon(Icons.Delete, "Delete", tint = W.copy(alpha = 0.6f)) }
                }
            }
        }
    }
}

@Composable
private fun StrengthRing(p: Float) {
    Box(Modifier.size(38.dp), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(progress = { 1f }, modifier = Modifier.size(38.dp), color = W.copy(alpha = 0.1f), strokeWidth = 4.dp)
        CircularProgressIndicator(progress = { p.coerceAtLeast(0.04f) }, modifier = Modifier.size(38.dp),
            color = if (p >= 0.7f) Neon.Gold else Neon.Cyan, strokeWidth = 4.dp, trackColor = Color.Transparent)
        Text("${(p * 100).toInt()}", color = W, fontSize = 10.sp)
    }
}

private fun articleTint(a: String) = when (a) { "der" -> Color(0xFF82B1FF); "die" -> Color(0xFFFF8A80); else -> Color(0xFFA5D6A7) }

private fun highlight(sentence: String, text: String) = buildAnnotatedString {
    val i = sentence.indexOf(text, ignoreCase = true)
    if (i < 0) { append(sentence); return@buildAnnotatedString }
    append(sentence.substring(0, i))
    withStyle(SpanStyle(color = Neon.Gold, fontWeight = FontWeight.Bold)) { append(sentence.substring(i, i + text.length)) }
    append(sentence.substring(i + text.length))
}

// =============================================================== review

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
fun ReviewScreen(vm: AppViewModel) {
    BackHandler { vm.endReview() }
    val w = vm.reviewQueue.getOrNull(vm.reviewIndex)
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
            IconButton(onClick = { vm.endReview() }) { Icon(Icons.Close, "End review", tint = W) }
            NeonTitle("Review", 24.sp, Modifier.weight(1f))
            Text("${minOf(vm.reviewIndex + 1, vm.reviewQueue.size)} / ${vm.reviewQueue.size}", color = W.copy(alpha = 0.7f))
        }
        // progress bar
        Box(Modifier.fillMaxWidth().padding(vertical = 8.dp).height(5.dp).clip(RoundedCornerShape(3.dp)).background(W.copy(alpha = 0.1f))) {
            val p = if (vm.reviewQueue.isEmpty()) 0f else vm.reviewIndex.toFloat() / vm.reviewQueue.size
            Box(Modifier.fillMaxWidth(p).height(5.dp).background(Neon.brush))
        }
        if (w == null) {
            ReviewFinished(vm)
            return@Column
        }
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // the moment in the video
            Box(
                Modifier.fillMaxWidth().aspectRatio(16f / 9f).clip(RoundedCornerShape(22.dp)).background(Color.Black)
            ) {
                if (vm.videoUri?.toString() == w.videoUri) {
                    AndroidView(
                        factory = { c ->
                            PlayerView(c).apply {
                                useController = false
                                resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                                player = vm.player
                                subtitleView?.visibility = android.view.View.GONE
                            }
                        },
                        onRelease = { it.player = null },
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    Column(Modifier.align(Alignment.Center), horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Movie, null, tint = Neon.Violet, modifier = Modifier.size(40.dp))
                        Text(w.videoName, color = W.copy(alpha = 0.7f), fontSize = 12.sp, maxLines = 1)
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            GlowButton("Hear it in the video", icon = Icons.Play) { vm.playClip(w) }
            Explain("Plays the line the word came from, on repeat. Listen first, then try to remember the meaning.",
                Modifier.padding(top = 8.dp, start = 8.dp, end = 8.dp))

            Spacer(Modifier.height(18.dp))
            Column(
                Modifier.fillMaxWidth().glass(RoundedCornerShape(26.dp)).padding(22.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(highlight(w.sentence, w.text), color = W, fontSize = 19.sp, textAlign = TextAlign.Center, lineHeight = 27.sp)
                Spacer(Modifier.height(14.dp))
                Row(verticalAlignment = Alignment.Bottom) {
                    if (w.article.isNotEmpty() && vm.reviewRevealed) Text(w.article + " ", color = articleTint(w.article), fontSize = 22.sp)
                    Text(w.text, color = Neon.Gold, fontSize = 30.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center)
                }
                IconButton(onClick = { vm.speak(w.text) }) { Icon(Icons.Volume, "Speak", tint = Neon.Cyan) }
                AnimatedVisibility(vm.reviewRevealed, enter = expandVertically() + fadeIn()) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        if (w.lemma.isNotEmpty() && w.lemma != w.text) Text("→ ${w.lemma}", color = W.copy(alpha = 0.8f), fontSize = 16.sp)
                        if (w.ipa.isNotEmpty()) Text(w.ipa, color = W.copy(alpha = 0.6f), fontSize = 15.sp)
                        Spacer(Modifier.height(8.dp))
                        if (w.english.isNotEmpty()) Text(w.english, color = W, fontSize = 17.sp, textAlign = TextAlign.Center)
                        if (w.persian.isNotEmpty()) CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                            Text(w.persian, color = W, fontSize = 19.sp, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 4.dp))
                        }
                        if (w.english.isEmpty() && w.persian.isEmpty()) Explain("No meaning was saved — tap the word in the video to look it up.")
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            Explain("Reviewed ${w.reviews}× so far · ${w.correct} correct", Modifier.padding(bottom = 8.dp))
        }
        // answer buttons
        if (!vm.reviewRevealed) {
            GlowButton("Show meaning", Modifier.fillMaxWidth().padding(vertical = 12.dp)) { vm.revealAnswer() }
        } else {
            Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(
                    Modifier.weight(1f).clip(RoundedCornerShape(50)).background(Neon.Pink.copy(alpha = 0.2f))
                        .clickable { vm.answer(false) }.padding(vertical = 14.dp),
                    contentAlignment = Alignment.Center
                ) { Text("Again · 10 min", color = Neon.Pink, fontWeight = FontWeight.Bold) }
                GlowButton("Got it · ${Srs.INTERVAL_DAYS[minOf(w.box + 1, Srs.INTERVAL_DAYS.size - 1)]} d", Modifier.weight(1f), icon = Icons.Check) { vm.answer(true) }
            }
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun ReviewFinished(vm: AppViewModel) {
    Column(Modifier.fillMaxWidth().padding(top = 40.dp).glass(RoundedCornerShape(28.dp)).padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.size(80.dp).background(Neon.brush, CircleShape), contentAlignment = Alignment.Center) {
            Icon(Icons.Check, null, tint = Color(0xFF0B0A1A), modifier = Modifier.size(44.dp))
        }
        Spacer(Modifier.height(16.dp))
        NeonTitle("Session complete", 24.sp)
        Spacer(Modifier.height(8.dp))
        Text("${vm.reviewDone} reviews · ${vm.reviewGot} remembered", color = W, fontSize = 16.sp)
        Explain("Words you knew come back later; the others come back sooner. Small daily sessions work best.",
            Modifier.padding(top = 8.dp))
        Spacer(Modifier.height(18.dp))
        GlowButton("Back to My Words") { vm.endReview() }
    }
}
