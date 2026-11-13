package com.behrouz.subplayer.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.PracticeMode
import com.behrouz.subplayer.Question
import com.behrouz.subplayer.Screen

private val L = Color(0xFFEDEBF5)
private val Good = Color(0xFF5BE38A)

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
fun PracticeScreen(vm: AppViewModel) {
    BackHandler { if (vm.practiceMode != null) vm.endPractice() else vm.screen = Screen.WORDS }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().imePadding().padding(horizontal = 16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
            IconButton(onClick = { if (vm.practiceMode != null) vm.endPractice() else vm.screen = Screen.WORDS }) {
                Icon(if (vm.practiceMode != null) Icons.Close else Icons.Back, "Back", tint = L)
            }
            NeonTitle(vm.practiceMode?.title ?: "Practice", 24.sp, Modifier.weight(1f))
            if (vm.practiceMode != null && vm.qIndex < vm.questions.size) {
                Text("${vm.qIndex + 1} / ${vm.questions.size}", color = L.copy(alpha = 0.7f))
            } else Text("🔥 ${vm.streak}", color = Neon.Gold, fontWeight = FontWeight.Bold, fontSize = 18.sp)
        }
        when {
            vm.practiceMode == null -> Hub(vm)
            vm.qIndex >= vm.questions.size -> Finished(vm)
            else -> {
                Box(Modifier.fillMaxWidth().padding(vertical = 8.dp).height(5.dp).clip(RoundedCornerShape(3.dp)).background(L.copy(alpha = 0.1f))) {
                    Box(Modifier.fillMaxWidth(vm.qIndex.toFloat() / vm.questions.size).height(5.dp).background(Neon.brush))
                }
                when (val q = vm.questions[vm.qIndex]) {
                    is Question.Gap -> GapQuestion(vm, q)
                    is Question.Dictation -> DictationQuestion(vm, q)
                    is Question.Article -> ArticleQuestion(vm, q)
                }
            }
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun Hub(vm: AppViewModel) {
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {
        Explain("Short sessions of up to 10 questions built from your own saved words — weakest words first. " +
            "Every answer counts towards your daily streak.", Modifier.padding(start = 12.dp, bottom = 14.dp, end = 4.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatBox("Streak", "${vm.streak} 🔥", Modifier.weight(1f))
            StatBox("Today", "${vm.todayCount}", Modifier.weight(1f))
            StatBox("Words", "${vm.words.size}", Modifier.weight(1f))
        }
        Spacer(Modifier.height(14.dp))
        PracticeMode.values().forEach { m ->
            val n = vm.available(m)
            Column(Modifier.fillMaxWidth().padding(vertical = 6.dp).glass(RoundedCornerShape(24.dp)).padding(18.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(44.dp).background(Neon.brush, CircleShape), contentAlignment = Alignment.Center) {
                        Text(when (m) { PracticeMode.GAPS -> "_ _"; PracticeMode.DICTATION -> "✎"; PracticeMode.ARTICLES -> "d·d" },
                            color = Color(0xFF0B0A1A), fontWeight = FontWeight.Black)
                    }
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text(m.title, color = L, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        Explain(m.explain)
                    }
                }
                Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Explain(if (n == 0) when (m) {
                        PracticeMode.ARTICLES -> "Save nouns to unlock"
                        PracticeMode.GAPS -> "Save words (add sentences for more variety)"
                        else -> "Save words to unlock"
                    } else "$n word${if (n == 1) "" else "s"} ready", Modifier.weight(1f))
                    GlowButton("Start", enabled = n > 0) { vm.startPractice(m) }
                }
            }
        }
        Spacer(Modifier.height(10.dp))
        Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).padding(16.dp)) {
            Text("Also try while watching", color = L, fontWeight = FontWeight.SemiBold)
            Explain("• Pause each line — the video stops after every subtitle so you can read and tap words.\n" +
                "• 🎙 Shadowing — a line plays, then pauses so you can repeat it aloud, again and again.\n" +
                "• Dictation trains your ear; add Beispielsätze to words for richer gap-fills.", Modifier.padding(top = 6.dp))
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun StatBox(label: String, value: String, modifier: Modifier) {
    Column(modifier.glass(RoundedCornerShape(18.dp)).padding(vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, color = L, fontSize = 20.sp, fontWeight = FontWeight.Black)
        Text(label, color = L.copy(alpha = 0.6f), fontSize = 11.sp)
    }
}

// --------------------------------------------------------------- gap fill

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun GapQuestion(vm: AppViewModel, q: Question.Gap) {
    var typed by remember(q) { mutableStateOf("") }
    var chosen by remember(q) { mutableStateOf<String?>(null) }
    var hint by remember(q) { mutableStateOf(false) }
    val fb = vm.feedback
    Column(Modifier.fillMaxWidth().weight1().verticalScroll(rememberScrollState())) {
        Column(Modifier.fillMaxWidth().padding(top = 8.dp).glass(RoundedCornerShape(26.dp)).padding(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally) {
            val c = q.cloze
            Text(buildAnnotatedString {
                append(c.before)
                withStyle(SpanStyle(color = if (fb == null) Neon.Cyan else if (fb.correct) Good else Neon.Pink, fontWeight = FontWeight.Bold)) {
                    append(if (fb == null) " ＿＿＿＿ " else c.answer)
                }
                append(c.after)
            }, color = L, fontSize = 21.sp, textAlign = TextAlign.Center, lineHeight = 30.sp)
            Spacer(Modifier.height(10.dp))
            if (fb == null && hint) Text("Starts with „${c.answer.take(2)}…“ · ${c.answer.length} letters", color = Neon.Gold, fontSize = 14.sp)
            if (fb != null) {
                if (c.en.isNotEmpty()) Text(c.en, color = L.copy(alpha = 0.75f), fontSize = 14.sp, textAlign = TextAlign.Center)
                if (c.fa.isNotEmpty()) CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    Text(c.fa, color = L.copy(alpha = 0.85f), fontSize = 16.sp, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                }
                Row(Modifier.padding(top = 6.dp)) { Pill("Speak", icon = Icons.Volume) { vm.speak(c.sentence) } }
            }
        }
        Spacer(Modifier.height(14.dp))
        if (q.choices.isNotEmpty()) {
            q.choices.forEach { ch ->
                val isAnswer = ch.equals(q.cloze.answer, ignoreCase = true)
                val color = when {
                    fb == null -> Color.White.copy(alpha = 0.08f)
                    isAnswer -> Good.copy(alpha = 0.35f)
                    ch == chosen -> Neon.Pink.copy(alpha = 0.35f)
                    else -> Color.White.copy(alpha = 0.05f)
                }
                Box(Modifier.fillMaxWidth().padding(vertical = 5.dp).clip(RoundedCornerShape(18.dp)).background(color)
                    .clickable(enabled = fb == null) { chosen = ch; vm.answerText(ch) }.padding(16.dp),
                    contentAlignment = Alignment.Center) { Text(ch, color = L, fontSize = 18.sp, fontWeight = FontWeight.SemiBold) }
            }
        } else if (fb == null) {
            GlassField(typed, { typed = it }, "Type the missing word")
            Spacer(Modifier.height(10.dp))
            GlowButton("Check", Modifier.fillMaxWidth(), enabled = typed.isNotBlank()) { vm.answerText(typed) }
        }
        if (fb == null) {
            Row(Modifier.padding(top = 8.dp)) { Pill("Hint") { hint = true } }
        }
        FeedbackBar(vm)
    }
}

// --------------------------------------------------------------- dictation

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DictationQuestion(vm: AppViewModel, q: Question.Dictation) {
    var typed by remember(q) { mutableStateOf("") }
    val fb = vm.feedback
    Column(Modifier.fillMaxWidth().weight1().verticalScroll(rememberScrollState())) {
        Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f).clip(RoundedCornerShape(22.dp)).background(Color.Black)) {
            if (vm.videoUri?.toString() == q.word.videoUri) {
                AndroidView(factory = { c ->
                    PlayerView(c).apply {
                        useController = false; resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT; player = vm.player
                        subtitleView?.visibility = android.view.View.GONE
                    }
                }, onRelease = { it.player = null }, modifier = Modifier.fillMaxSize())
            } else {
                Text(q.word.videoName, color = L.copy(alpha = 0.6f), modifier = Modifier.align(Alignment.Center))
            }
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Pill("▶ Play again") { vm.replayDictation() }
            Pill(if (vm.speed < 1f) "Slow ✓" else "Slow", active = vm.speed < 1f) { vm.cycleSpeed() }
        }
        Explain("The line repeats until you check. Type everything you hear — umlauts can be typed as ae/oe/ue, ß as ss.")
        Spacer(Modifier.height(10.dp))
        if (fb == null) {
            GlassField(typed, { typed = it }, "What do you hear?", singleLine = false)
            Spacer(Modifier.height(10.dp))
            GlowButton("Check", Modifier.fillMaxWidth(), enabled = typed.isNotBlank()) { vm.answerText(typed) }
        } else {
            Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).padding(18.dp)) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    fb.marks.forEach { m ->
                        Text(m.word, color = if (m.ok) Good else Neon.Pink, fontSize = 19.sp, fontWeight = FontWeight.SemiBold,
                            modifier = Modifier.padding(vertical = 2.dp))
                    }
                }
                Text("You typed: $typed", color = L.copy(alpha = 0.6f), fontSize = 13.sp, modifier = Modifier.padding(top = 8.dp))
            }
        }
        FeedbackBar(vm)
    }
}

// --------------------------------------------------------------- articles

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun ArticleQuestion(vm: AppViewModel, q: Question.Article) {
    val fb = vm.feedback
    Column(Modifier.fillMaxWidth().weight1(), horizontalAlignment = Alignment.CenterHorizontally) {
        Spacer(Modifier.height(30.dp))
        Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(28.dp)).padding(30.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(if (fb == null) "___  ${q.word.lemma}" else "${q.word.article}  ${q.word.lemma}", color = L, fontSize = 34.sp, fontWeight = FontWeight.Black)
            if (q.word.english.isNotEmpty()) Text(q.word.english, color = L.copy(alpha = 0.6f), fontSize = 14.sp, textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 8.dp))
            Row(Modifier.padding(top = 6.dp)) { Pill("Speak", icon = Icons.Volume) { vm.speak(if (fb != null) "${q.word.article} ${q.word.lemma}" else q.word.lemma) } }
        }
        Spacer(Modifier.height(24.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            listOf("der" to Color(0xFF82B1FF), "die" to Color(0xFFFF8A80), "das" to Color(0xFFA5D6A7)).forEach { (a, c) ->
                val bg = when {
                    fb == null -> c.copy(alpha = 0.18f)
                    a == q.word.article -> Good.copy(alpha = 0.4f)
                    else -> Color.White.copy(alpha = 0.05f)
                }
                Box(Modifier.weight(1f).clip(RoundedCornerShape(20.dp)).background(bg).clickable(enabled = fb == null) { vm.answerText(a) }
                    .padding(vertical = 22.dp), contentAlignment = Alignment.Center) {
                    Text(a, color = c, fontSize = 24.sp, fontWeight = FontWeight.Black)
                }
            }
        }
        Explain("Tip: blue = der, red = die, green = das — the word cards use the same colours.", Modifier.padding(top = 14.dp))
        FeedbackBar(vm)
    }
}

// --------------------------------------------------------------- shared

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun FeedbackBar(vm: AppViewModel) {
    val fb = vm.feedback ?: return
    Spacer(Modifier.height(14.dp))
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background((if (fb.correct) Good else Neon.Pink).copy(alpha = 0.18f)).padding(16.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Text(if (fb.correct) "✓" else "✗", color = if (fb.correct) Good else Neon.Pink, fontSize = 26.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.width(12.dp))
        Text(fb.detail, color = L, fontSize = 16.sp, modifier = Modifier.weight(1f))
    }
    Spacer(Modifier.height(12.dp))
    GlowButton(if (vm.qIndex + 1 < vm.questions.size) "Next" else "Finish", Modifier.fillMaxWidth()) { vm.nextQuestion() }
    Spacer(Modifier.height(16.dp))
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun Finished(vm: AppViewModel) {
    Column(Modifier.fillMaxWidth().padding(top = 40.dp).glass(RoundedCornerShape(28.dp)).padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally) {
        Text("🔥", fontSize = 54.sp)
        NeonTitle("${vm.practiceScore} / ${vm.questions.size} correct", 26.sp)
        Explain("Streak: ${vm.streak} day${if (vm.streak == 1) "" else "s"} · ${vm.todayCount} answers today", Modifier.padding(top = 8.dp))
        Spacer(Modifier.height(18.dp))
        GlowButton("Another round") { vm.practiceMode?.let { vm.startPractice(it) } }
        Spacer(Modifier.height(10.dp))
        Pill("Back to practice") { vm.endPractice() }
    }
}

/** Column weight helper (keeps the call sites short). */
@Composable
private fun Modifier.weight1(): Modifier = this
