package com.behrouz.subplayer.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.media3.common.util.UnstableApi
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.Engine
import com.behrouz.subplayer.Sheet
import com.behrouz.subplayer.data.Assets
import com.behrouz.subplayer.dict.Dictionary

// ============================================================== word card

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun WordSheet(vm: AppViewModel, s: Sheet.Word) {
    ModalBottomSheet(onDismissRequest = { vm.closeSheet() }, sheetState = rememberModalBottomSheetState()) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 20.dp)
        ) {
            when {
                s.loading -> Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                s.needDictionary -> NeedDictionary(vm, s)
                s.entries.isEmpty() -> NotFound(vm, s)
                else -> s.entries.forEachIndexed { i, e ->
                    if (i > 0) HorizontalDivider(Modifier.padding(vertical = 14.dp))
                    EntryView(vm, e)
                }
            }
            Spacer(Modifier.height(10.dp))
            Text(
                "Dictionary: Wiktionary (CC BY-SA 4.0)",
                style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline
            )
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun EntryView(vm: AppViewModel, e: Dictionary.Entry) {
    // headword
    Row(verticalAlignment = Alignment.Bottom) {
        if (e.article.isNotEmpty()) {
            Text(e.article + " ", style = MaterialTheme.typography.headlineSmall, color = articleColor(e.article))
        }
        Text(e.lemma, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
    }
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 2.dp)) {
        Text(e.posDe, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.tertiary)
        if (e.ipa.isNotEmpty()) {
            Spacer(Modifier.width(10.dp))
            Text(e.ipa, fontFamily = FontFamily.Serif, fontSize = 17.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (e.hyphenation.isNotEmpty()) {
            Spacer(Modifier.width(10.dp))
            Text(e.hyphenation, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.outline)
        }
    }
    // pronunciation + links
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
        FilledTonalButton(onClick = { vm.speak(e.lemma) }) {
            Icon(Icons.Volume, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Speak")
        }
        OutlinedButton(onClick = { vm.speak(e.lemma, slow = true) }) { Text("Slow") }
        if (e.audioUrl.isNotEmpty()) {
            OutlinedButton(onClick = { vm.playRecording(e.audioUrl) }) {
                Icon(Icons.Play, null, Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Recording")
            }
        }
        OutlinedButton(onClick = { vm.openDwds(e.lemma) }) {
            Text("DWDS"); Spacer(Modifier.width(4.dp)); Icon(Icons.OpenIn, null, Modifier.size(16.dp))
        }
    }

    if (e.english.isNotEmpty()) {
        Section("English")
        e.english.take(6).forEachIndexed { i, g -> Text("${i + 1}. $g", style = MaterialTheme.typography.bodyLarge) }
    }

    Section("فارسی")
    PersianBlock(vm, e)

    if (e.senses.isNotEmpty()) {
        Section("Bedeutungen")
        e.senses.forEachIndexed { i, sense ->
            Text("${i + 1}. ${sense.de}", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 4.dp))
            sense.examples.forEach { ex ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        ex, fontStyle = FontStyle.Italic, style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f).padding(start = 14.dp)
                    )
                    IconButton(onClick = { vm.speak(cleanExample(ex)) }, modifier = Modifier.size(36.dp)) {
                        Icon(Icons.Volume, "Speak example", Modifier.size(18.dp))
                    }
                }
            }
        }
    }
    if (e.synonyms.isNotEmpty()) {
        Section("Synonyme")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            e.synonyms.forEach { syn -> SuggestionChip(onClick = { vm.openWord(syn, syn) }, label = { Text(syn) }) }
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun PersianBlock(vm: AppViewModel, e: Dictionary.Entry) {
    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
        Column(Modifier.fillMaxWidth()) {
            when {
                e.persian.isNotEmpty() -> Text(e.persian.joinToString("، "), fontSize = 19.sp)
                e.persianViaEnglish.isNotEmpty() -> {
                    Text(e.persianViaEnglish.joinToString("، "), fontSize = 18.sp)
                    Text(
                        "از طریق معنای انگلیسی (via English)",
                        style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline
                    )
                }
                else -> Text(
                    "ترجمهٔ فارسی در فرهنگ آفلاین نیست",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.outline
                )
            }
        }
    }
    val s = vm.sheet as? Sheet.Word
    if (e.persian.isEmpty() && s != null) OnlineWordTranslation(vm, s)
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun OnlineWordTranslation(vm: AppViewModel, s: Sheet.Word) {
    when {
        s.onlineBusy -> Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 6.dp)) {
            CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
            Spacer(Modifier.width(8.dp)); Text("Translating online…", style = MaterialTheme.typography.bodySmall)
        }
        s.onlineEn != null -> Column(Modifier.padding(top = 6.dp)) {
            Text("Online: ${s.onlineEn}", style = MaterialTheme.typography.bodyMedium)
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                Text(s.onlineFa ?: "", fontSize = 18.sp, modifier = Modifier.fillMaxWidth())
            }
        }
        else -> TextButton(onClick = { vm.translateWordOnline() }) { Text("Translate online (needs internet)") }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun NeedDictionary(vm: AppViewModel, s: Sheet.Word) {
    Text(s.word, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
    Spacer(Modifier.height(8.dp))
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
        Column(Modifier.padding(16.dp)) {
            Text("Offline dictionary not downloaded yet", style = MaterialTheme.typography.titleSmall)
            Text(
                "About ${Assets.DICT_DE.sizeMb} MB, once. Then every word works without internet: " +
                    "IPA, meanings, examples, English and Persian.",
                style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(vertical = 6.dp)
            )
            Button(onClick = { vm.downloadDictionary() }, enabled = vm.task == null) {
                Icon(Icons.Download, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Download dictionary")
            }
        }
    }
    QuickActions(vm, s)
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun NotFound(vm: AppViewModel, s: Sheet.Word) {
    Text(s.word, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.SemiBold)
    Text(
        "Not in the offline dictionary (names and rare words may be missing).",
        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(vertical = 6.dp)
    )
    QuickActions(vm, s)
    OnlineWordTranslation(vm, s)
}

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun QuickActions(vm: AppViewModel, s: Sheet.Word) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 10.dp)) {
        FilledTonalButton(onClick = { vm.speak(s.word) }) {
            Icon(Icons.Volume, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Speak")
        }
        OutlinedButton(onClick = { vm.openDwds(s.word) }) {
            Text("DWDS"); Spacer(Modifier.width(4.dp)); Icon(Icons.OpenIn, null, Modifier.size(16.dp))
        }
    }
}

// ============================================================ phrase card

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PhraseSheet(vm: AppViewModel, s: Sheet.Phrase) {
    ModalBottomSheet(onDismissRequest = { vm.closeSheet() }, sheetState = rememberModalBottomSheetState()) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 20.dp)
        ) {
            Text(s.text, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilledTonalButton(onClick = { vm.speak(s.text) }) {
                    Icon(Icons.Volume, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("Speak")
                }
                OutlinedButton(onClick = { vm.speak(s.text, slow = true) }) { Text("Slow") }
            }
            when {
                s.busy -> Row(Modifier.padding(top = 14.dp), verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp)); Text("Translating…")
                }
                s.error != null -> Text(
                    s.error, color = MaterialTheme.colorScheme.secondary,
                    style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 12.dp)
                )
                else -> {
                    Section("English")
                    Text(s.en ?: "", style = MaterialTheme.typography.bodyLarge)
                    Section("فارسی")
                    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                        Text(s.fa ?: "", fontSize = 19.sp, modifier = Modifier.fillMaxWidth())
                    }
                    Text(
                        "Machine translation · ${s.service ?: ""}",
                        style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                }
            }
            if (s.words.isNotEmpty()) {
                Section("Word by word")
                s.words.forEach { w ->
                    Surface(
                        shape = RoundedCornerShape(10.dp),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.surfaceVariant),
                        modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp).clickable { vm.openWord(w, s.text) }
                    ) {
                        Row(Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                            Text(w, fontWeight = FontWeight.SemiBold, modifier = Modifier.width(120.dp))
                            Text(s.glosses[w].orEmpty().ifEmpty { "tap for details" },
                                color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                        }
                    }
                }
            }
        }
    }
}

// ======================================================= generate subtitles

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GenerateSheet(vm: AppViewModel) {
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 20.dp)) {
            Text("Make subtitles", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            Text(
                "Runs on your phone, offline. Each model downloads once.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Section("Spoken language")
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf("de" to "Deutsch", "en" to "English").forEachIndexed { i, (code, label) ->
                    SegmentedButton(
                        selected = vm.genLang == code, onClick = { vm.genLang = code },
                        shape = SegmentedButtonDefaults.itemShape(i, 2)
                    ) { Text(label) }
                }
            }
            Section("Quality")
            Engine.values().forEach { e ->
                val enabled = e == Engine.FAST || vm.whisperSupported
                val asset = when (e) {
                    Engine.FAST -> if (vm.genLang == "de") Assets.VOSK_DE else Assets.VOSK_EN
                    Engine.ACCURATE -> Assets.WHISPER_BASE
                    Engine.BEST -> Assets.WHISPER_SMALL
                }
                val ready = vm.assetReady(asset)
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = if (vm.genEngine == e) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerHigh,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                        .clickable(enabled = enabled) { vm.genEngine = e }
                ) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected = vm.genEngine == e, onClick = { vm.genEngine = e }, enabled = enabled)
                        Column(Modifier.weight(1f)) {
                            Text(if (e == Engine.ACCURATE) "${e.title}  · recommended" else e.title,
                                style = MaterialTheme.typography.titleSmall)
                            Text(
                                if (!enabled) "Needs a newer phone processor (ARMv8.2)" else e.detail,
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Text(
                            if (ready) "✓ ready" else "${asset.sizeMb} MB",
                            style = MaterialTheme.typography.labelMedium,
                            color = if (ready) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.outline
                        )
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            Button(onClick = { vm.generate() }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Subtitles, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Start")
            }
        }
    }
}

// ================================================================ export

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
fun ExportDialog(vm: AppViewModel) {
    var burn by remember { mutableStateOf(vm.cues.isNotEmpty()) }
    AlertDialog(
        onDismissRequest = { vm.sheet = null },
        title = { Text("Save A–B clip") },
        text = {
            Column {
                Text("${fmt(vm.pointA)} → ${fmt(vm.pointB)} will be saved as a new video in Movies/SubPlayer.")
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 10.dp)) {
                    Checkbox(checked = burn, onCheckedChange = { burn = it }, enabled = vm.cues.isNotEmpty())
                    Text(if (vm.cues.isNotEmpty()) "Burn subtitles into the video" else "No subtitles to burn in")
                }
            }
        },
        confirmButton = { Button(onClick = { vm.export(burn) }) { Text("Save") } },
        dismissButton = { TextButton(onClick = { vm.sheet = null }) { Text("Cancel") } }
    )
}

// ================================================================ helpers

@Composable
private fun Section(title: String) {
    Text(
        title.uppercase(),
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.primary,
        letterSpacing = 1.sp,
        modifier = Modifier.padding(top = 16.dp, bottom = 4.dp)
    )
}

@Composable
private fun articleColor(a: String) = when (a) {
    "der" -> androidx.compose.ui.graphics.Color(0xFF82B1FF)
    "die" -> androidx.compose.ui.graphics.Color(0xFFFF8A80)
    else -> androidx.compose.ui.graphics.Color(0xFFA5D6A7)
}

/** Wiktionary examples start with a sense marker like "[1]" — remove it before speaking. */
private fun cleanExample(s: String) = s.replace(Regex("""^\[\d+[a-z]?]\s*"""), "")
