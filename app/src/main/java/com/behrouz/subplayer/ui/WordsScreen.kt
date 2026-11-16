package com.behrouz.subplayer.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
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
    LaunchedEffect(vm.words.size) { vm.loadWordInfo() }
    var cat by remember { mutableStateOf("All") }
    var video by remember { mutableStateOf<String?>(null) }
    var day by remember { mutableStateOf<Long?>(null) }
    var showCal by remember { mutableStateOf(false) }
    val filtered = vm.words.filter { w ->
        (cat == "All" || vm.category(w) == cat) && (video == null || w.videoName == video) && (day == null || dayOf(w.created) == day)
    }
    vm.exportList = filtered
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
            Spacer(Modifier.height(10.dp))
            Row(Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).clickable { vm.openPractice() }.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Text("🔥", fontSize = 26.sp)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("Practice · ${vm.streak}-day streak", color = W, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                    Explain("Fill the gap · dictation · der/die/das — ${vm.todayCount} answered today")
                }
                Icon(Icons.Next, null, tint = W.copy(alpha = 0.7f))
            }
            Spacer(Modifier.height(12.dp))
            ReminderCard(vm)
            Spacer(Modifier.height(10.dp))
            if (vm.words.isNotEmpty()) {
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("YOUR WORDS · ${filtered.size}", color = Neon.Cyan, fontSize = 12.sp, letterSpacing = 1.5.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    Pill(if (day != null) "📅 " + dayLabel(day!!) else "📅 Calendar", active = showCal || day != null) { if (day != null) { day = null; showCal = false } else showCal = !showCal }
                    Spacer(Modifier.width(6.dp))
                    Pill("Export", icon = Icons.Share) { vm.sheet = com.behrouz.subplayer.Sheet.WordsExport }
                }
                if (showCal) MonthCalendar(vm.words.map { dayOf(it.created) }, day) { d -> day = if (day == d) null else d }
                Row(Modifier.fillMaxWidth().padding(top = 8.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("All", "Nouns", "Verbs", "Adjectives", "Phrases", "Other").forEach { c ->
                        val n = if (c == "All") vm.words.size else vm.words.count { vm.category(it) == c }
                        if (n > 0 || c == "All") Pill("$c $n", active = cat == c) { cat = c }
                    }
                }
                val videos = vm.words.map { it.videoName }.filter { it.isNotEmpty() }.groupingBy { it }.eachCount().entries.sortedByDescending { it.value }
                if (videos.size > 1) Row(Modifier.fillMaxWidth().padding(top = 6.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Pill("All videos", active = video == null) { video = null }
                    videos.take(25).forEach { (v, n) -> Pill(v.substringBeforeLast('.').take(28) + " · $n", active = video == v) { video = if (video == v) null else v } }
                }
                Spacer(Modifier.height(6.dp))
            }
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
        items(filtered, key = { it.id }) { w -> WordCard(vm, w, now) }
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
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
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
                var snap by remember(w.uid) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
                LaunchedEffect(w.uid) {
                    vm.snapshot(w)?.let { f -> snap = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                        android.graphics.BitmapFactory.decodeFile(f.path)?.asImageBitmap() } }
                }
                snap?.let { b ->
                    Box(Modifier.fillMaxWidth().padding(bottom = 10.dp).clip(RoundedCornerShape(16.dp)).clickable { vm.playClip(w, stayOnScreen = false) }) {
                        androidx.compose.foundation.Image(b, "The video at ${fmt(w.startMs)}", Modifier.fillMaxWidth().aspectRatio(b.width.toFloat() / b.height.coerceAtLeast(1)),
                            contentScale = androidx.compose.ui.layout.ContentScale.Crop)
                        Text("▶ ${fmt(w.startMs)}", color = W, fontSize = 12.sp, modifier = Modifier.align(Alignment.BottomStart).padding(8.dp)
                            .background(Color.Black.copy(alpha = 0.55f), RoundedCornerShape(8.dp)).padding(horizontal = 6.dp, vertical = 2.dp))
                    }
                }
                Text("${vm.category(w)} · saved ${java.text.SimpleDateFormat("d MMM yyyy", java.util.Locale.US).format(java.util.Date(w.created))}",
                    color = Neon.Cyan.copy(alpha = 0.8f), fontSize = 12.sp, modifier = Modifier.padding(bottom = 4.dp))
                if (w.ipa.isNotEmpty()) Text(w.ipa, color = W.copy(alpha = 0.7f), fontSize = 15.sp)
                Text(highlight(w.sentence, w.text), color = W.copy(alpha = 0.9f), fontStyle = FontStyle.Italic,
                    modifier = Modifier.padding(vertical = 8.dp))
                Explain("From “${w.videoName}” at ${fmt(w.startMs)} · reviewed ${w.reviews}× (${w.correct} correct)" +
                    if (w.lastReview > 0) " · last ${Srs.dueLabel(w.lastReview, now).replace("in ", "")} ago".replace("due now ago", "just now") else "")
                val extra = vm.wordExamples[w.id].orEmpty()
                if (extra.isNotEmpty()) {
                    Text("MORE SENTENCES", color = Neon.Cyan, fontSize = 11.sp, letterSpacing = 1.2.sp, fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(top = 10.dp, bottom = 2.dp))
                    extra.forEach { e ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f).padding(vertical = 4.dp)) {
                                Text(highlight(e.de, w.text), color = W, fontSize = 14.sp)
                                if (e.en.isNotEmpty()) Text(e.en, color = W.copy(alpha = 0.6f), fontSize = 12.sp)
                                if (e.fa.isNotEmpty()) CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                                    Text(e.fa, color = W.copy(alpha = 0.75f), fontSize = 14.sp, modifier = Modifier.fillMaxWidth())
                                }
                            }
                            IconButton(onClick = { vm.speak(e.de, lang = w.lang) }, modifier = Modifier.size(34.dp)) { Icon(Icons.Volume, "Speak", tint = Neon.Cyan, modifier = Modifier.size(18.dp)) }
                            IconButton(onClick = { vm.deleteExample(e) }, modifier = Modifier.size(34.dp)) { Icon(Icons.Close, "Remove", tint = W.copy(alpha = 0.5f), modifier = Modifier.size(16.dp)) }
                        }
                    }
                }
                androidx.compose.foundation.layout.FlowRow(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    val lw = w.lemma.ifEmpty { w.text }
                    Pill("ChatGPT") { vm.learnMore(AppViewModel.Source.CHATGPT, lw, w.sentence, w.lang) }
                    Pill("Gemini") { vm.learnMore(AppViewModel.Source.GEMINI, lw, w.sentence, w.lang) }
                    Pill("DeepSeek") { vm.learnMore(AppViewModel.Source.DEEPSEEK, lw, w.sentence, w.lang) }
                    Pill("Grok") { vm.learnMore(AppViewModel.Source.GROK, lw, w.sentence, w.lang) }
                    if (w.lang == "en") Pill("Cambridge") { vm.learnMore(AppViewModel.Source.CAMBRIDGE, lw, w.sentence, w.lang) }
                    else Pill("DWDS") { vm.learnMore(AppViewModel.Source.DWDS, lw, w.sentence, w.lang) }
                    Pill("dict.cc") { vm.learnMore(AppViewModel.Source.DICTCC, lw, w.sentence, w.lang) }
                    Pill("＋ Add sentences", active = true) { vm.openAddSentences(w) }
                    Pill("Where else?", icon = Icons.Search) { vm.openUses(if (w.text.contains(' ')) w.text else w.lemma.ifEmpty { w.text }, w.lang) }
                }
                Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Pill("Play in video", icon = Icons.Play) { vm.playClip(w, stayOnScreen = false) }
                    Pill("Speak", icon = Icons.Volume) { vm.speak(if (w.text.contains(' ')) w.text else w.lemma.ifEmpty { w.text }, lang = w.lang) }
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

fun dayOf(ms: Long): Long = (ms + java.util.TimeZone.getDefault().getOffset(ms)) / 86_400_000L

private fun dayLabel(d: Long): String = java.text.SimpleDateFormat("d MMM", java.util.Locale.US).apply { timeZone = java.util.TimeZone.getTimeZone("UTC") }
    .format(java.util.Date(d * 86_400_000L))

/** A month of the calendar: how many words were saved each day; tap a day to see its words. */
@Composable
private fun MonthCalendar(days: List<Long>, selected: Long?, onPick: (Long) -> Unit) {
    var offset by remember { mutableIntStateOf(0) }
    val counts = remember(days) { days.groupingBy { it }.eachCount() }
    val utc = java.util.TimeZone.getTimeZone("UTC")
    val cal = java.util.Calendar.getInstance(utc).apply {
        timeInMillis = dayOf(System.currentTimeMillis()) * 86_400_000L
        set(java.util.Calendar.DAY_OF_MONTH, 1); add(java.util.Calendar.MONTH, offset)
    }
    val first = cal.timeInMillis / 86_400_000L
    val daysIn = cal.getActualMaximum(java.util.Calendar.DAY_OF_MONTH)
    val lead = (cal.get(java.util.Calendar.DAY_OF_WEEK) + 5) % 7          // Monday first
    val title = java.text.SimpleDateFormat("MMMM yyyy", java.util.Locale.US).apply { timeZone = utc }.format(cal.time)
    val max = (0 until daysIn).maxOfOrNull { counts[first + it] ?: 0 }?.coerceAtLeast(1) ?: 1
    Column(Modifier.fillMaxWidth().padding(top = 8.dp).glass(RoundedCornerShape(20.dp)).padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { offset-- }) { Text("‹", color = W, fontSize = 22.sp) }
            Text(title, color = W, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center, modifier = Modifier.weight(1f))
            IconButton(onClick = { if (offset < 0) offset++ }) { Text("›", color = if (offset < 0) W else W.copy(alpha = 0.2f), fontSize = 22.sp) }
        }
        Row(Modifier.fillMaxWidth()) {
            listOf("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su").forEach { Text(it, color = W.copy(alpha = 0.5f), fontSize = 11.sp, textAlign = TextAlign.Center, modifier = Modifier.weight(1f)) }
        }
        val cells = lead + daysIn
        for (row in 0 until (cells + 6) / 7) {
            Row(Modifier.fillMaxWidth()) {
                for (col in 0 until 7) {
                    val k = row * 7 + col - lead
                    Box(Modifier.weight(1f).aspectRatio(1f).padding(2.dp), contentAlignment = Alignment.Center) {
                        if (k in 0 until daysIn) {
                            val d = first + k; val n = counts[d] ?: 0
                            val bg = when {
                                d == selected -> Neon.Gold
                                n > 0 -> Neon.Violet.copy(alpha = 0.25f + 0.6f * n / max)
                                else -> Color.Transparent
                            }
                            Column(Modifier.fillMaxSize().clip(RoundedCornerShape(10.dp)).background(bg).clickable(enabled = n > 0) { onPick(d) },
                                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                                Text("${k + 1}", color = if (d == selected) Color(0xFF0B0A1A) else if (n > 0) W else W.copy(alpha = 0.4f), fontSize = 13.sp,
                                    fontWeight = if (n > 0) FontWeight.Bold else FontWeight.Normal)
                                if (n > 0) Text("$n", color = if (d == selected) Color(0xFF0B0A1A) else Neon.Cyan, fontSize = 9.sp)
                            }
                        }
                    }
                }
            }
        }
        Explain("${days.count { it in first until first + daysIn }} words saved this month · tap a day to see them", Modifier.padding(top = 4.dp))
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
    // each review shows another of the word's sentences (video line first, then the added ones)
    val shown = w?.let { vm.sentencesOf(it).let { list -> list[it.reviews % list.size] } }
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
                Text(highlight(shown?.de ?: w.sentence, w.text), color = W, fontSize = 19.sp, textAlign = TextAlign.Center, lineHeight = 27.sp)
                Spacer(Modifier.height(14.dp))
                Row(verticalAlignment = Alignment.Bottom) {
                    if (w.article.isNotEmpty() && vm.reviewRevealed) Text(w.article + " ", color = articleTint(w.article), fontSize = 22.sp)
                    Text(w.text, color = Neon.Gold, fontSize = 30.sp, fontWeight = FontWeight.Black, textAlign = TextAlign.Center)
                }
                IconButton(onClick = { vm.speak(w.text, lang = w.lang) }) { Icon(Icons.Volume, "Speak", tint = Neon.Cyan) }
                AnimatedVisibility(vm.reviewRevealed, enter = expandVertically() + fadeIn()) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        if (w.lemma.isNotEmpty() && w.lemma != w.text) Text("→ ${w.lemma}", color = W.copy(alpha = 0.8f), fontSize = 16.sp)
                        if (w.ipa.isNotEmpty()) Text(w.ipa, color = W.copy(alpha = 0.6f), fontSize = 15.sp)
                        Spacer(Modifier.height(8.dp))
                        if (w.english.isNotEmpty()) Text(w.english, color = W, fontSize = 17.sp, textAlign = TextAlign.Center)
                        if (shown != null && shown.en.isNotEmpty()) Text("„${shown.en}“", color = W.copy(alpha = 0.7f), fontSize = 14.sp,
                            textAlign = TextAlign.Center, modifier = Modifier.padding(top = 4.dp))
                        if (w.persian.isNotEmpty()) CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                            Text(w.persian, color = W, fontSize = 19.sp, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 4.dp))
                        }
                        if (w.english.isEmpty() && w.persian.isEmpty()) Explain("No meaning was saved — tap the word in the video to look it up.")
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            Explain("Reviewed ${w.reviews}× so far · ${w.correct} correct · ${vm.sentencesOf(w).size} sentence(s)", Modifier.padding(bottom = 8.dp))
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
