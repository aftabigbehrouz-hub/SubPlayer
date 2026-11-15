package com.behrouz.subplayer.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
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
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.media3.common.util.UnstableApi
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.PracticeMode
import com.behrouz.subplayer.Screen
import com.behrouz.subplayer.Sheet
import com.behrouz.subplayer.learn.Levels
import com.behrouz.subplayer.learn.Library
import com.behrouz.subplayer.net.Catalog
import java.util.Locale

private val L = Color.White
private val Dark = Color(0xFF0B0A1A)
private val Fg = Color(0xFFEDEBF5)

fun levelColor(lv: Int) = Color(Levels.COLORS[lv.coerceIn(0, 6)])

@Composable
fun LevelChip(lv: Int, approx: Boolean = false) {
    if (lv <= 0) return
    Text(Levels.NAMES[lv] + if (approx) "≈" else "", color = Dark, fontWeight = FontWeight.Bold, fontSize = 11.sp,
        modifier = Modifier.background(levelColor(lv), RoundedCornerShape(6.dp)).padding(horizontal = 5.dp, vertical = 1.dp))
}

@Composable
private fun Title(text: String) {
    Text(text.uppercase(Locale.ROOT), color = Neon.Cyan, fontSize = 12.sp, letterSpacing = 1.3.sp, fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(top = 16.dp, bottom = 6.dp))
}

/** "1:02.345" ↔ milliseconds. */
fun fmtMs(ms: Long): String {
    val m = ms.coerceAtLeast(0)
    val s = m / 1000
    return if (s >= 3600) String.format(Locale.US, "%d:%02d:%02d.%03d", s / 3600, (s / 60) % 60, s % 60, m % 1000)
    else String.format(Locale.US, "%d:%02d.%03d", s / 60, s % 60, m % 1000)
}

fun parseMs(t: String): Long? {
    val m = Regex("""^\s*(?:(\d+):)?(?:(\d+):)?(\d+)(?:[.,](\d{1,3}))?\s*$""").find(t) ?: return null
    val a = m.groupValues[1]; val b = m.groupValues[2]
    val (h, mi) = if (b.isNotEmpty()) (a.toLongOrNull() ?: 0) to b.toLong() else 0L to (a.toLongOrNull() ?: 0)
    return ((h * 60 + mi) * 60 + m.groupValues[3].toLong()) * 1000 + m.groupValues[4].padEnd(3, '0').ifEmpty { "000" }.toLong()
}

// ============================================================ where else is the word used?

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UsesSheet(vm: AppViewModel, s: Sheet.Uses) {
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = Fg) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 16.dp)) {
            NeonTitle("„${s.word}“ in your videos", 22.sp)
            Explain("Every subtitle line of your videos (made or loaded in SubPlayer, also on your other devices) where it is said. " +
                "Tap a line to watch that moment.", Modifier.padding(top = 4.dp))
            if (s.busy) {
                Row(Modifier.padding(24.dp), verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = Neon.Cyan)
                    Spacer(Modifier.width(12.dp)); Text("Searching your subtitles…", color = L)
                }
                return@Column
            }
            val groups = s.uses.groupBy { it.item.key }
            Text(if (s.uses.isEmpty()) "Not found in ${s.files} subtitle file${if (s.files == 1) "" else "s"}"
                 else "${s.uses.size}${if (s.uses.size >= 300) "+" else ""} line${if (s.uses.size == 1) "" else "s"} in ${groups.size} video${if (groups.size == 1) "" else "s"} · ${s.files} searched",
                color = Neon.Gold, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 10.dp))
            if (s.note.isNotEmpty()) Explain(s.note, Modifier.padding(top = 2.dp))
            val openable = remember(s.uses) { groups.mapValues { (_, list) -> vm.canOpen(list.first()) } }
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 520.dp).padding(top = 8.dp)) {
                groups.forEach { (key, list) ->
                    item(key = "h$key") {
                        Row(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Movie, null, tint = Neon.Violet, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(list.first().item.name, color = L, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                            if (openable[key] != true) Text("open it once", color = L.copy(alpha = 0.45f), fontSize = 11.sp)
                        }
                    }
                    items(list, key = { "${key}_${it.index}" }) { u ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 3.dp).glass(RoundedCornerShape(14.dp), 0.06f).clickable { vm.openUse(u) }
                            .padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(fmt(u.startMs), color = Neon.Cyan, fontSize = 12.sp, modifier = Modifier.width(52.dp))
                            Text(buildAnnotatedString {
                                var at = 0
                                for (r in u.spans.sortedBy { it.first }) {
                                    if (r.first < at || r.last >= u.text.length) continue
                                    append(u.text.substring(at, r.first).replace('\n', ' '))
                                    withStyle(SpanStyle(color = Neon.Gold, fontWeight = FontWeight.Bold)) { append(u.text.substring(r.first, r.last + 1)) }
                                    at = r.last + 1
                                }
                                append(u.text.substring(at).replace('\n', ' '))
                            }, color = L.copy(alpha = if (openable[key] == true) 0.95f else 0.6f), fontSize = 15.sp)
                        }
                    }
                }
            }
        }
    }
}

// ============================================================ edit a subtitle line

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EditCueSheet(vm: AppViewModel, s: Sheet.EditCue) {
    val cue = vm.cues.getOrNull(s.index) ?: run { vm.sheet = null; return }
    var text by remember(s.index, cue) { mutableStateOf(cue.text) }
    var start by remember(s.index, cue) { mutableStateOf(fmtMs(cue.startMs)) }
    var end by remember(s.index, cue) { mutableStateOf(fmtMs(cue.endMs)) }
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = Fg) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().imePadding().padding(bottom = 20.dp)) {
            NeonTitle("Edit line ${s.index + 1} of ${vm.cues.size}", 22.sp)
            Explain("Fix what was heard wrongly, or the timing. Saved with the video (and synced, if Sync is on).", Modifier.padding(top = 4.dp, bottom = 10.dp))
            GlassField(text, { text = it }, "Text", singleLine = false)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Column(Modifier.weight(1f)) { GlassField(start, { start = it }, "Start") }
                Column(Modifier.weight(1f)) { GlassField(end, { end = it }, "End") }
            }
            Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                fun nudge(v: String, d: Long) = fmtMs(((parseMs(v) ?: 0) + d).coerceAtLeast(0))
                Pill("start −0.1") { start = nudge(start, -100) }
                Pill("+0.1") { start = nudge(start, 100) }
                Spacer(Modifier.weight(1f))
                Pill("end −0.1") { end = nudge(end, -100) }
                Pill("+0.1") { end = nudge(end, 100) }
            }
            Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Pill("Start = now") { start = fmtMs(vm.player.currentPosition) }
                Pill("End = now") { end = fmtMs(vm.player.currentPosition) }
                Pill("▶ Play", icon = Icons.Play) { vm.playCue(s.index) }
            }
            Spacer(Modifier.height(14.dp))
            GlowButton("Save", Modifier.fillMaxWidth(), icon = Icons.Check) {
                val a = parseMs(start); val b = parseMs(end)
                if (a == null || b == null) vm.message = "Times look like 1:02.500 (minutes:seconds.milliseconds)"
                else vm.saveCue(s.index, text, a, b)
            }
            Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("◀ Previous line") { if (s.index > 0) vm.sheet = Sheet.EditCue(s.index - 1) }
                Pill("Next line ▶") { if (s.index + 1 < vm.cues.size) vm.sheet = Sheet.EditCue(s.index + 1) }
            }
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("＋ New line after") { vm.insertCueAfter(s.index) }
                Pill("Delete line", icon = Icons.Delete) { vm.deleteCue(s.index) }
            }
        }
    }
}

// ============================================================ transcript

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TranscriptSheet(vm: AppViewModel) {
    val state = rememberLazyListState()
    LaunchedEffect(Unit) { if (vm.currentCue > 2) state.scrollToItem(vm.currentCue - 2) }
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = Fg) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp).navigationBarsPadding()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                NeonTitle("Transcript", 22.sp, Modifier.weight(1f))
                Text("${vm.cues.size} lines", color = L.copy(alpha = 0.6f), fontSize = 12.sp)
            }
            Explain("Tap a line to jump there · ✎ to correct it · the translation shows when it is on.", Modifier.padding(bottom = 8.dp))
            LazyColumn(state = state, modifier = Modifier.fillMaxWidth().heightIn(max = 600.dp), contentPadding = PaddingValues(bottom = 20.dp)) {
                itemsIndexed(vm.cues) { i, c ->
                    val now = i == vm.currentCue
                    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp).clip(RoundedCornerShape(12.dp))
                        .background(if (now) Neon.Violet.copy(alpha = 0.25f) else Color.Transparent)
                        .clickable { vm.seekTo(c.startMs); vm.player.play() }.padding(horizontal = 8.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Text(fmt(c.startMs), color = Neon.Cyan, fontSize = 12.sp, modifier = Modifier.width(50.dp))
                        Column(Modifier.weight(1f)) {
                            Text(c.text.replace('\n', ' '), color = L, fontSize = 15.sp)
                            if (vm.showTranslation) vm.translationFor(i)?.let { t ->
                                CompositionLocalProvider(LocalLayoutDirection provides if (vm.trLang() == "fa") LayoutDirection.Rtl else LayoutDirection.Ltr) {
                                    Text(t, color = Neon.Gold.copy(alpha = 0.85f), fontSize = 13.sp, modifier = Modifier.fillMaxWidth())
                                }
                            }
                        }
                        IconButton(onClick = { vm.player.pause(); vm.sheet = Sheet.EditCue(i) }, modifier = Modifier.size(36.dp)) {
                            Icon(Icons.Edit, "Edit", tint = L.copy(alpha = 0.6f), modifier = Modifier.size(16.dp))
                        }
                    }
                }
            }
        }
    }
}

// ============================================================ player options

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun PlayerOptionsSheet(vm: AppViewModel) {
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = Fg) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 24.dp)) {
            NeonTitle("Player options", 22.sp)

            Title("Speed")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(0.5f, 0.6f, 0.75f, 0.9f, 1f, 1.25f, 1.5f).forEach { v -> Pill(speedLabel(v), active = vm.speed == v) { vm.setSpeed(v) } }
            }

            Title("Repeat (A–B and Loop line)")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(0 to "Until I stop", 2 to "2×", 3 to "3×", 5 to "5×", 10 to "10×").forEach { (n, t) -> Pill(t, active = vm.loopTimes == n) { vm.loopTimes = n } }
            }
            Explain("After that many times the video plays on.", Modifier.padding(top = 4.dp))

            Title("Word levels (A1 – C2)")
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Colour the words in the subtitles", color = L, modifier = Modifier.weight(1f))
                Switch(vm.showLevels, { vm.toggleLevels() }, colors = SwitchDefaults.colors(checkedTrackColor = Neon.Violet))
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.padding(top = 6.dp)) {
                (1..6).forEach { lv ->
                    Text(Levels.NAMES[lv], color = if (vm.minLevel <= lv) Dark else L.copy(alpha = 0.5f), fontWeight = FontWeight.Bold,
                        modifier = Modifier.clip(RoundedCornerShape(50)).background(if (vm.minLevel <= lv) levelColor(lv) else Color.White.copy(alpha = 0.08f))
                            .clickable { vm.setMinLevel(lv) }.padding(horizontal = 12.dp, vertical = 6.dp))
                }
            }
            Explain("Tap a level to colour only words from that level up (B1 = hide the easy A1/A2 colours). " +
                "English: ${Levels.source("en")}. German: ${Levels.source("de")}.", Modifier.padding(top = 6.dp))

            Title("Translation under the subtitles")
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Show the translation line", color = L, modifier = Modifier.weight(1f))
                Switch(vm.showTranslation, { vm.toggleTranslation() }, colors = SwitchDefaults.colors(checkedTrackColor = Neon.Violet))
            }
            Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("fa", "en", "de").forEach { t -> Pill(vm.langLabel(t), active = vm.trTarget == t) { vm.setTranslationTarget(t) } }
            }
            Explain(if (vm.trAllDone) "This video is translated into ${vm.langLabel(vm.trLang())} and saved — works offline."
                    else "Lines are translated as they come (needs internet). Translate all does the whole video now, before you watch, and keeps it.",
                Modifier.padding(top = 6.dp))
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                GlowButton(if (vm.trAllDone) "Translate again" else "Translate all now", enabled = vm.cues.isNotEmpty() && vm.task == null) { vm.translateAll() }
                if (vm.trAllDone) Pill("Remove") { vm.deleteTranslation() }
            }

            Title("Subtitle timing")
            Explain("Subtitles too early or too late? Move every line.", Modifier.padding(bottom = 6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("−1 s") { vm.shiftAll(-1000) }; Pill("−0.25 s") { vm.shiftAll(-250) }
                Pill("+0.25 s") { vm.shiftAll(250) }; Pill("+1 s") { vm.shiftAll(1000) }
            }

            Title("Subtitles")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("Transcript", icon = Icons.Notes) { vm.sheet = Sheet.Transcript }
                Pill("Edit this line", icon = Icons.Edit) { vm.editCurrentLine() }
                Pill("Study this video", icon = Icons.School) { vm.sheet = null; vm.openStudy() }
                Pill("Save .srt", icon = Icons.Download) { vm.exportSrt() }
                Pill("Share .srt", icon = Icons.Share) { vm.shareSrt() }
            }
            Explain("Keyboard: Space = play/pause, ← → = 5 s.", Modifier.padding(top = 12.dp))
        }
    }
}

// ============================================================ Discover

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DiscoverScreen(vm: AppViewModel) {
    BackHandler { if (vm.searchResults != null) { vm.discoverQuery = ""; vm.searchDiscover() } else vm.screen = Screen.PLAYER }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 40.dp)) {
        item {
            Row(Modifier.fillMaxWidth().statusBarsPadding().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { vm.screen = Screen.PLAYER }) { Icon(Icons.Back, "Back", tint = L) }
                NeonTitle("Discover", 26.sp, Modifier.weight(1f))
                Pill("Deutsch", active = vm.discoverLang == "de") { vm.setDiscoverLanguage("de") }
                Spacer(Modifier.width(6.dp))
                Pill("English", active = vm.discoverLang == "en") { vm.setDiscoverLanguage("en") }
            }
            Explain(if (vm.discoverLang == "de")
                "Programmes of ARD, ZDF, 3sat, Arte, DW, KiKA, phoenix and the regional stations that they offer as files. CC = with the broadcaster's own subtitles. Downloads go to Movies/SubPlayer."
                else "VOA Learning English (public domain, an archive since 2025), NASA videos (public domain, mostly with subtitles) and podcasts: BBC Learning English, BBC World Service, PBS, TED, NPR — 🎧 = audio, saved to Music/SubPlayer.",
                Modifier.padding(start = 12.dp, end = 4.dp, bottom = 10.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    vm.discoverQuery, { vm.discoverQuery = it }, singleLine = true, modifier = Modifier.weight(1f),
                    placeholder = { Text(if (vm.discoverLang == "de") "Search: Terra X, Wetter, Maus …" else "Search: climate, 6 Minute English, Mars …") },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), keyboardActions = KeyboardActions(onSearch = { vm.searchDiscover() }),
                    shape = RoundedCornerShape(18.dp),
                    colors = OutlinedTextFieldDefaults.colors(focusedTextColor = L, unfocusedTextColor = L, focusedBorderColor = Neon.Cyan,
                        unfocusedBorderColor = L.copy(alpha = 0.25f), cursorColor = Neon.Cyan, focusedPlaceholderColor = L.copy(alpha = 0.4f),
                        unfocusedPlaceholderColor = L.copy(alpha = 0.4f))
                )
                Spacer(Modifier.width(8.dp))
                Box(Modifier.size(52.dp).background(Neon.brush, CircleShape).clickable { vm.searchDiscover() }, contentAlignment = Alignment.Center) {
                    Icon(Icons.Search, "Search", tint = Dark)
                }
            }
            if (vm.discoverLang == "de") Row(Modifier.padding(top = 8.dp)) { Pill("Only with subtitles (CC)", active = vm.subsOnly) { vm.subsOnly = !vm.subsOnly; if (vm.searchResults != null) vm.searchDiscover() } }
        }
        val results = vm.searchResults
        if (vm.searchBusy) item { Row(Modifier.padding(24.dp)) { CircularProgressIndicator(color = Neon.Cyan) } }
        else if (results != null) {
            item {
                Row(Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(if (vm.searchError.isNotEmpty()) vm.searchError else "${results.size} found", color = Neon.Gold, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                    TextButton(onClick = { vm.discoverQuery = ""; vm.searchDiscover() }) { Text("Back to suggestions", color = Neon.Cyan) }
                }
            }
            items(results.distinctBy { it.link + "|" + it.title }, key = { it.link + "|" + it.title }) { f -> FilmRow(vm, f) }
        } else {
            vm.shelves().forEach { sh ->
                item(key = sh.title) {
                    Column(Modifier.padding(top = 18.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(sh.title, color = L, fontWeight = FontWeight.Bold, fontSize = 17.sp, modifier = Modifier.weight(1f))
                            Text(sh.level, color = Neon.Gold, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        }
                        Explain(sh.why)
                        val films = vm.shelfFilms[sh.title]; val err = vm.shelfErrors[sh.title]
                        when {
                            err != null -> Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
                                Text(err, color = Neon.Pink, fontSize = 13.sp, modifier = Modifier.weight(1f))
                                TextButton(onClick = { vm.loadShelves(force = true) }) { Text("Try again", color = Neon.Cyan) }
                            }
                            films == null -> Box(Modifier.padding(12.dp)) { CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Neon.Cyan) }
                            films.isEmpty() -> Explain("Nothing new here right now.", Modifier.padding(top = 6.dp))
                            else -> LazyRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                items(films.distinctBy { it.link + "|" + it.title }, key = { it.link + "|" + it.title }) { f -> FilmCard(vm, f) }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Badges(f: Catalog.Film) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(f.label, color = Dark, fontSize = 11.sp, fontWeight = FontWeight.Black,
            modifier = Modifier.background(Neon.brush, RoundedCornerShape(6.dp)).padding(horizontal = 6.dp, vertical = 1.dp))
        if (f.hasSubtitles || f.channel == "NASA") Text("CC", color = Neon.Cyan, fontSize = 11.sp, fontWeight = FontWeight.Bold,
            modifier = Modifier.border(1.dp, Neon.Cyan, RoundedCornerShape(5.dp)).padding(horizontal = 4.dp))
        if (f.audio) Text("🎧", fontSize = 12.sp)
        if (f.length.isNotEmpty()) Text(f.length, color = L.copy(alpha = 0.6f), fontSize = 11.sp)
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun FilmCard(vm: AppViewModel, f: Catalog.Film) {
    Column(Modifier.width(230.dp).glass(RoundedCornerShape(18.dp)).clickable { vm.sheet = Sheet.FilmInfo(f) }.padding(12.dp)) {
        Badges(f)
        Text(f.title, color = L, fontWeight = FontWeight.SemiBold, fontSize = 14.sp, maxLines = 2, overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp).heightIn(min = 38.dp))
        Text(listOf(f.topic, f.date).filter { it.isNotEmpty() }.joinToString(" · "), color = L.copy(alpha = 0.55f), fontSize = 11.sp, maxLines = 1,
            overflow = TextOverflow.Ellipsis)
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun FilmRow(vm: AppViewModel, f: Catalog.Film) {
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp).glass(RoundedCornerShape(18.dp)).clickable { vm.sheet = Sheet.FilmInfo(f) }.padding(12.dp)) {
        Badges(f)
        Text(f.title, color = L, fontWeight = FontWeight.SemiBold, fontSize = 15.sp, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 4.dp))
        Text(listOf(f.topic, f.date).filter { it.isNotEmpty() }.joinToString(" · "), color = L.copy(alpha = 0.55f), fontSize = 12.sp, maxLines = 1)
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FilmInfoSheet(vm: AppViewModel, s: Sheet.FilmInfo) {
    val f = s.film
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, containerColor = SheetBg, contentColor = Fg) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 24.dp)) {
            Badges(f)
            Text(f.title, color = L, fontWeight = FontWeight.Bold, fontSize = 20.sp, modifier = Modifier.padding(top = 8.dp))
            Text(listOf(f.topic, f.date).filter { it.isNotEmpty() }.joinToString(" · "), color = L.copy(alpha = 0.6f), fontSize = 13.sp)
            if (f.description.isNotEmpty()) Text(f.description, color = L.copy(alpha = 0.85f), fontSize = 14.sp, modifier = Modifier.padding(top = 10.dp))
            Explain(when {
                f.audio -> "Audio (podcast episode). After the download, tap Subtitles to transcribe it, then learn with it like a video."
                f.hasSubtitles || f.channel == "NASA" -> "Comes with the broadcaster's own subtitles — they are loaded with the video, no transcribing needed."
                else -> "No subtitles from the broadcaster: after the download, tap Subtitles to transcribe it."
            }, Modifier.padding(top = 12.dp))
            Spacer(Modifier.height(14.dp))
            GlowButton(if (f.audio) "Download & listen" else "Download & watch", Modifier.fillMaxWidth(), icon = Icons.Download, enabled = vm.task == null) { vm.importFilm(f) }
            if (f.urlWebsite.isNotEmpty()) TextButton(onClick = { vm.openUrl(f.urlWebsite) }) { Text("Open the web page", color = Neon.Cyan) }
            Explain("For your own learning. The programmes belong to their broadcasters.", Modifier.padding(top = 4.dp))
        }
    }
}

// ============================================================ study a video

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun StudyScreen(vm: AppViewModel) {
    BackHandler { vm.screen = Screen.PLAYER }
    var tab by remember { mutableIntStateOf(0) }
    var level by remember { mutableIntStateOf(0) }       // 0 = all
    var notSaved by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 16.dp)) {
        Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = { vm.screen = Screen.PLAYER }) { Icon(Icons.Back, "Back", tint = L) }
            Column(Modifier.weight(1f)) {
                NeonTitle("Study this video", 22.sp)
                Text(vm.videoName, color = L.copy(alpha = 0.6f), fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        Row(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Pill("Words", active = tab == 0) { tab = 0 }
            Pill("My words (${vm.videoWords().size})", active = tab == 1) { tab = 1 }
            Pill("Practise", active = tab == 2) { tab = 2 }
        }
        when (tab) {
            0 -> {
                if (vm.studyBusy) { Row(Modifier.padding(24.dp)) { CircularProgressIndicator(color = Neon.Cyan) }; return@Column }
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Pill("All", active = level == 0) { level = 0 }
                    (1..6).forEach { lv ->
                        val n = vm.studyWords.count { it.level == lv }
                        Text("${Levels.NAMES[lv]} $n", color = if (level == lv) Dark else levelColor(lv), fontWeight = FontWeight.Bold, fontSize = 13.sp,
                            modifier = Modifier.clip(RoundedCornerShape(50)).background(if (level == lv) levelColor(lv) else Color.White.copy(alpha = 0.07f))
                                .clickable { level = lv }.padding(horizontal = 12.dp, vertical = 8.dp))
                    }
                }
                Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Pill("Not saved yet", active = notSaved) { notSaved = !notSaved }
                    Spacer(Modifier.width(10.dp))
                    Explain("Tap a word: meaning, save with its moment.", Modifier.weight(1f))
                }
                val list = vm.studyWords.filter { (level == 0 || it.level == level) && (!notSaved || !vm.isKnownWord(it.shown)) }
                LazyColumn(Modifier.fillMaxWidth().weight(1f).padding(top = 6.dp), contentPadding = PaddingValues(bottom = 20.dp)) {
                    items(list, key = { it.shown }) { w ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 2.dp).glass(RoundedCornerShape(14.dp), 0.05f).clickable { vm.studyWordCard(w.shown) }
                            .padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.width(34.dp)) { LevelChip(w.level, approx = vm.wordLang() == "de") }
                            Text(w.shown, color = if (vm.isKnownWord(w.shown)) Neon.Gold else L, fontSize = 16.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
                            if (vm.isKnownWord(w.shown)) Icon(Icons.Star, "Saved", tint = Neon.Gold, modifier = Modifier.size(16.dp))
                            Text("${w.count}×", color = L.copy(alpha = 0.55f), fontSize = 12.sp, modifier = Modifier.padding(horizontal = 8.dp))
                            IconButton(onClick = { vm.openUses(w.shown, vm.wordLang()) }, modifier = Modifier.size(32.dp)) {
                                Icon(Icons.Search, "Where else", tint = Neon.Cyan, modifier = Modifier.size(16.dp))
                            }
                        }
                    }
                }
            }
            1 -> {
                val mine = vm.videoWords()
                if (mine.isEmpty()) Explain("No words saved from this video yet. Pause, tap a word, ★ Save — or pick them in the Words tab.", Modifier.padding(12.dp))
                LazyColumn(Modifier.fillMaxWidth().weight(1f), contentPadding = PaddingValues(bottom = 20.dp)) {
                    items(mine.sortedBy { it.startMs }, key = { it.id }) { w ->
                        Column(Modifier.fillMaxWidth().padding(vertical = 3.dp).glass(RoundedCornerShape(16.dp), 0.06f).clickable { vm.playClip(w, stayOnScreen = false) }.padding(12.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(fmt(w.startMs), color = Neon.Cyan, fontSize = 12.sp, modifier = Modifier.width(48.dp))
                                Text((if (w.article.isNotEmpty()) w.article + " " else "") + w.lemma.ifEmpty { w.text }, color = Neon.Gold, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                                Text(vm.category(w), color = L.copy(alpha = 0.5f), fontSize = 11.sp)
                            }
                            val meaning = listOf(w.english, w.persian).filter { it.isNotBlank() }.joinToString("  ·  ")
                            if (meaning.isNotEmpty()) Text(meaning, color = L.copy(alpha = 0.8f), fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            Text(w.sentence.replace('\n', ' '), color = L.copy(alpha = 0.6f), fontSize = 13.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }
            else -> Column(Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState())) {
                Explain("Practise with the whole text of this video — the lines you heard, the words of your level — besides your saved words and their added sentences.",
                    Modifier.padding(start = 8.dp, bottom = 12.dp))
                Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).padding(16.dp)) {
                    Text(PracticeMode.TEXT_GAPS.title, color = L, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                    Explain("A line of the video with one word missing — words from this level up:")
                    Row(Modifier.padding(vertical = 8.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        (1..6).forEach { lv ->
                            Text(Levels.NAMES[lv] + "+", color = if (vm.textMinLevel == lv) Dark else levelColor(lv), fontWeight = FontWeight.Bold,
                                modifier = Modifier.clip(RoundedCornerShape(50)).background(if (vm.textMinLevel == lv) levelColor(lv) else Color.White.copy(alpha = 0.07f))
                                    .clickable { vm.textMinLevel = lv }.padding(horizontal = 12.dp, vertical = 7.dp))
                        }
                    }
                    GlowButton("Start", enabled = !vm.studyBusy) { vm.startTextPractice(PracticeMode.TEXT_GAPS) }
                }
                Spacer(Modifier.height(10.dp))
                Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).padding(16.dp)) {
                    Text(PracticeMode.TEXT_DICTATION.title, color = L, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                    Explain(PracticeMode.TEXT_DICTATION.explain)
                    Spacer(Modifier.height(8.dp))
                    GlowButton("Start") { vm.startTextPractice(PracticeMode.TEXT_DICTATION) }
                }
                Spacer(Modifier.height(10.dp))
                Column(Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).clickable { vm.openPractice() }.padding(16.dp)) {
                    Text("Your saved words", color = L, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                    Explain("Fill the gap with their video lines and added sentences, dictation, der/die/das — the Practice page.")
                }
            }
        }
    }
}

// ============================================================ export My Words

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WordsExportSheet(vm: AppViewModel) {
    var format by remember { mutableStateOf("csv") }
    val list = vm.exportList
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, containerColor = SheetBg, contentColor = Fg) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 24.dp)) {
            NeonTitle("Export ${list.size} word${if (list.size == 1) "" else "s"}", 22.sp)
            Explain("The words shown in the list now (with your filters): word, base form, meaning, Persian, sentence, video and time.", Modifier.padding(top = 4.dp, bottom = 10.dp))
            listOf("csv" to "Spreadsheet (.csv) — Excel, Google Sheets", "txt" to "Text (.txt) — to read or print", "anki" to "Anki (.txt) — flash cards: front = word + sentence, back = meaning")
                .forEach { (k, t) ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp).glass(RoundedCornerShape(14.dp), if (format == k) 0.16f else 0.05f).clickable { format = k }.padding(12.dp)) {
                        Text(if (format == k) "●" else "○", color = Neon.Cyan, modifier = Modifier.width(22.dp)); Text(t, color = L)
                    }
                }
            Spacer(Modifier.height(12.dp))
            GlowButton("Share…", Modifier.fillMaxWidth(), icon = Icons.Share) { vm.sheet = null; vm.shareWords(format, list) }
            Spacer(Modifier.height(8.dp))
            Pill("Save to Download/SubPlayer", icon = Icons.Download) { vm.sheet = null; vm.saveWordsToDownloads(format, list) }
        }
    }
}
