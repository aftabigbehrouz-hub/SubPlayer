package com.behrouz.subplayer.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.media3.common.util.UnstableApi
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.Sheet
import com.behrouz.subplayer.learn.Teacher

private val TL = Color(0xFFEDEBF5)

/** The AIs the teacher can ask. OTHER = only copy the question (for any other assistant). */
val TEACHER_AIS = listOf(
    AppViewModel.Source.CHATGPT to "ChatGPT", AppViewModel.Source.GEMINI to "Gemini", AppViewModel.Source.DEEPSEEK to "DeepSeek",
    AppViewModel.Source.GROK to "Grok", AppViewModel.Source.GAPGPT to "GapGPT", AppViewModel.Source.OTHER to "Copy only"
)

@Composable
private fun Label(t: String) = Text(t, color = Neon.Cyan, fontSize = 11.sp, letterSpacing = 1.sp, fontWeight = FontWeight.Bold,
    modifier = Modifier.padding(top = 14.dp, bottom = 6.dp))

/** The teacher: explain the word / the sentence, check my sentence, answer my question, TestDaF questions — by any online AI. */
@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun TeacherSheet(vm: AppViewModel, s: Sheet.Teacher) {
    var extra by remember(s.wordId, s.mode) { mutableStateOf(if (s.mode == Teacher.Mode.SENTENCE) s.sentence.replace('\n', ' ') else "") }
    var typed by remember(s.wordId, s.mode) { mutableStateOf("") }
    val aiName = TEACHER_AIS.firstOrNull { it.first == vm.teacherAi }?.second ?: "ChatGPT"
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = TL) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)
            .navigationBarsPadding().imePadding().padding(bottom = 24.dp)) {
            NeonTitle("Teacher", 24.sp)
            Text("„${s.word}“" + if (s.lemma != s.word) "  (${s.lemma})" else "", color = Neon.Gold, fontWeight = FontWeight.SemiBold)
            Label("ANSWER FROM")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                TEACHER_AIS.forEach { (src, name) -> Pill(name, active = vm.teacherAi == src) { vm.chooseTeacherAi(src) } }
            }
            Label("WHAT")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Teacher.Mode.values().forEach { m -> Pill(m.title, active = s.mode == m) { vm.teacherMode(m) } }
            }
            Explain(when (s.mode) {
                Teacher.Mode.WORD -> "Meaning, forms, 8 collocations and 5 sentences. Pasting the answer saves the collocations and sentences to the word."
                Teacher.Mode.SENTENCE -> "The sentence explained: translation, structure, cases, words worth learning, three new sentences."
                Teacher.Mode.CHECK -> "Write your own sentence with the word; the AI corrects it and explains why."
                Teacher.Mode.ASK -> "Any question about the word, the line or the video."
                Teacher.Mode.EXAM -> "6 TestDaF-style questions on this word. Pasting the answer puts them into Review."
            }, Modifier.padding(top = 8.dp, bottom = 4.dp))
            when (s.mode) {
                Teacher.Mode.SENTENCE -> GlassField(extra, { extra = it }, "Sentence", singleLine = false)
                Teacher.Mode.CHECK -> GlassField(extra, { extra = it }, "My sentence with „${s.lemma}“", singleLine = false)
                Teacher.Mode.ASK -> GlassField(extra, { extra = it }, "My question", singleLine = false)
                else -> {}
            }
            Spacer(Modifier.height(10.dp))
            GlowButton(if (vm.teacherAi == AppViewModel.Source.OTHER) "1 · Copy the question" else "1 · Ask $aiName", Modifier.fillMaxWidth(),
                icon = Icons.School) { vm.askTeacher(s, extra) }
            Spacer(Modifier.height(8.dp))
            GlowButton("2 · Paste answer", Modifier.fillMaxWidth(), icon = Icons.Check, enabled = true) { vm.pasteTeacher(s, typed) }
            Explain("In $aiName: copy the whole answer (the copy button under it), come back and tap Paste answer. " +
                "If copying doesn't work, paste it into the box below by hand first.", Modifier.padding(top = 6.dp))
            GlassField(typed, { typed = it }, "…or paste the answer here", singleLine = false)
            if (s.note.isNotBlank()) Text(s.note, color = Neon.Mint, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 12.dp))
            if (s.answer.isNotBlank()) {
                Label("ANSWER")
                SelectionContainer {
                    Text(s.answer, color = TL, fontSize = 15.sp, lineHeight = 21.sp,
                        modifier = Modifier.fillMaxWidth().glass(RoundedCornerShape(14.dp)).padding(12.dp))
                }
            }
            Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (s.wordId > 0) Pill("✎ Edit the word") { vm.sheet = Sheet.EditWord(s.wordId) }
                Pill("✎ Write a question") { vm.sheet = Sheet.NewQuestion(s.lang, s.lemma, s.video) }
            }
        }
    }
}

/** A word by hand, or the saved word changed: meanings, forms, collocations (one per line) and sentences. */
@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun EditWordSheet(vm: AppViewModel, s: Sheet.EditWord) {
    val w = remember(s.wordId) { vm.words.firstOrNull { it.id == s.wordId } }
    var text by remember(s.wordId) { mutableStateOf(w?.text ?: "") }
    var lemma by remember(s.wordId) { mutableStateOf(w?.lemma ?: "") }
    var article by remember(s.wordId) { mutableStateOf(w?.article ?: "") }
    var ipa by remember(s.wordId) { mutableStateOf(w?.ipa ?: "") }
    var english by remember(s.wordId) { mutableStateOf(w?.english ?: "") }
    var persian by remember(s.wordId) { mutableStateOf(w?.persian ?: "") }
    var lang by remember(s.wordId) { mutableStateOf(w?.lang ?: "de") }
    var cols by remember(s.wordId) { mutableStateOf("") }
    var sents by remember(s.wordId) { mutableStateOf("") }
    val have = remember(s.wordId, vm.wordInfoVersion) { w?.let { vm.collocationsOf(it) }.orEmpty() }
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = TL) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)
            .navigationBarsPadding().imePadding().padding(bottom = 24.dp)) {
            NeonTitle(if (w == null) "New word" else "Edit word", 24.sp)
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("Deutsch", active = lang == "de") { lang = "de" }
                Pill("English", active = lang == "en") { lang = "en" }
            }
            Spacer(Modifier.height(8.dp))
            GlassField(text, { text = it }, "Word or phrase")
            GlassField(lemma, { lemma = it }, "Base form (gehen for ging)")
            if (lang == "de") GlassField(article, { article = it }, "Article (der / die / das)")
            GlassField(ipa, { ipa = it }, "IPA")
            GlassField(english, { english = it }, "Meaning (English)", singleLine = false)
            GlassField(persian, { persian = it }, "معنی (فارسی)", singleLine = false)
            Label("COLLOCATIONS" + if (have.isNotEmpty()) " · ${have.size} saved" else "")
            if (have.isNotEmpty()) Text(have.joinToString("\n") { "• " + it.phrase }, color = Neon.Gold, fontSize = 13.sp, modifier = Modifier.padding(bottom = 6.dp))
            Explain("Add more, one per line:  phrase | meaning | example. A whole AI answer pasted here is sorted by itself.")
            GlassField(cols, { cols = it }, "New collocations", singleLine = false)
            Label("SENTENCES")
            Explain("One per line:  DE: … | EN: … | FA: …  — or plain sentences.")
            GlassField(sents, { sents = it }, "New sentences", singleLine = false)
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Pill("Paste into collocations") { cols = (cols.trimEnd() + "\n" + vm.clipboardText()).trim() }
                Pill("Paste into sentences") { sents = (sents.trimEnd() + "\n" + vm.clipboardText()).trim() }
            }
            Spacer(Modifier.height(12.dp))
            GlowButton("Save", Modifier.fillMaxWidth(), icon = Icons.Check, enabled = text.isNotBlank()) {
                vm.saveEditedWord(s.wordId, text, lemma, article, ipa, english, persian, lang, cols, sents)
            }
        }
    }
}

/** A TestDaF / IELTS question written by hand; it comes back in Review. */
@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NewQuestionSheet(vm: AppViewModel, s: Sheet.NewQuestion) {
    var q by remember(s) { mutableStateOf("") }
    var opts by remember(s) { mutableStateOf("") }
    var a by remember(s) { mutableStateOf("") }
    var e by remember(s) { mutableStateOf("") }
    ModalBottomSheet(onDismissRequest = { vm.sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = SheetBg, contentColor = TL) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)
            .navigationBarsPadding().imePadding().padding(bottom = 24.dp)) {
            NeonTitle("My question", 24.sp)
            if (s.lemma.isNotBlank()) Text("for „${s.lemma}“", color = Neon.Gold, fontWeight = FontWeight.SemiBold)
            Explain("It comes back in Review like a word. Leave the options empty for an open question.", Modifier.padding(vertical = 8.dp))
            GlassField(q, { q = it }, "Question (with its short text, if any)", singleLine = false)
            GlassField(opts, { opts = it }, "Options — one per line (optional)", singleLine = false)
            GlassField(a, { a = it }, "Answer (exactly as one option)")
            GlassField(e, { e = it }, "Why (optional)", singleLine = false)
            Spacer(Modifier.height(12.dp))
            GlowButton("Put into Review", Modifier.fillMaxWidth(), icon = Icons.Check, enabled = q.isNotBlank() && a.isNotBlank()) {
                vm.saveOwnQuestion(s.lang, s.lemma, s.video, q, opts, a, e)
            }
        }
    }
}
