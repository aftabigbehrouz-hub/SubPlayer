package com.behrouz.subplayer.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.media3.common.util.UnstableApi
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.Sheet

private val Light = Color(0xFFEDEBF5)

/** Load / save / share the subtitle file. */
@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SubFileSheet(vm: AppViewModel, onLoadSrt: () -> Unit) {
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, containerColor = SheetBg, contentColor = Light) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp).navigationBarsPadding().padding(bottom = 24.dp)) {
            NeonTitle("Subtitle file", 24.sp)
            Explain(if (vm.cues.isEmpty()) "No subtitles yet — make them with Subtitles, or load an .srt file."
                else "${vm.cues.size} lines (${vm.langName(vm.cueLang)}). Every subtitle you make is also kept inside the app " +
                    "and reloads automatically with its video.", Modifier.padding(bottom = 14.dp))
            GlowButton("Save to Download folder", Modifier.fillMaxWidth(), icon = Icons.Download, enabled = vm.cues.isNotEmpty()) {
                vm.sheet = null; vm.exportSrt()
            }
            Explain("Saved as Download/SubPlayer/<video>.de.srt — open it with any file manager, VLC or a PC.", Modifier.padding(top = 6.dp, bottom = 12.dp))
            GlowButton("Share (Telegram, e-mail …)", Modifier.fillMaxWidth(), icon = Icons.Share, enabled = vm.cues.isNotEmpty()) {
                vm.sheet = null; vm.shareSrt()
            }
            Spacer(Modifier.height(12.dp))
            Pill("Load an .srt / .vtt file", icon = Icons.FileOpen) { vm.sheet = null; onLoadSrt() }
        }
    }
}

/** Paste sentences (e.g. from ChatGPT / Grok / DWDS) to add to a saved word. */
@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddSentencesSheet(vm: AppViewModel, s: Sheet.AddSentences) {
    var text by remember(s.wordId) { mutableStateOf(s.initial) }
    val preview = remember(text) { vm.previewSentences(text) }
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = Light) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)
            .navigationBarsPadding().imePadding().padding(bottom = 24.dp)) {
            NeonTitle("Add sentences", 24.sp)
            Text("for „${s.title}“", color = Neon.Gold, fontWeight = FontWeight.SemiBold)
            Explain("Paste the answer from ChatGPT, Grok, DWDS or dict.cc. Lines like  DE: … | EN: … | FA: …  are read with their " +
                "translations; plain German sentences work too. Whatever you copied is already pasted below.", Modifier.padding(vertical = 8.dp))
            GlassField(text, { text = it }, "Sentences", singleLine = false)
            Row(Modifier.padding(top = 8.dp)) {
                Pill("Paste from clipboard") { text = vm.clipboardText() }
            }
            Text(if (preview.isEmpty()) "No sentences recognised yet" else "${preview.size} sentence${if (preview.size == 1) "" else "s"} found:",
                color = Light, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 14.dp, bottom = 6.dp))
            preview.forEach { e ->
                Column(Modifier.fillMaxWidth().padding(vertical = 4.dp).glass(RoundedCornerShape(14.dp)).padding(12.dp)) {
                    Text(e.de, color = Light, fontSize = 15.sp)
                    if (e.en.isNotEmpty()) Text(e.en, color = Light.copy(alpha = 0.7f), fontSize = 13.sp)
                    if (e.fa.isNotEmpty()) CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                        Text(e.fa, color = Light.copy(alpha = 0.85f), fontSize = 15.sp, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            GlowButton("Add ${preview.size} to this word", Modifier.fillMaxWidth(), icon = Icons.Check, enabled = preview.isNotEmpty()) {
                vm.addSentences(s.wordId, text)
            }
        }
    }
}
