package com.behrouz.subplayer.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.Sheet
import java.util.Locale

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(
    vm: AppViewModel,
    fullscreen: Boolean,
    onToggleFullscreen: () -> Unit,
    onOpenVideo: () -> Unit,
    onLoadSrt: () -> Unit
) {
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(vm.message) {
        vm.message?.let { snack.showSnackbar(it); vm.message = null }
    }

    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.fillMaxSize()) {
            if (!fullscreen) TopBar(vm, onOpenVideo)

            // ------------------------------------------------ video + subtitles
            Box(
                Modifier.fillMaxWidth().weight(1f).background(Color.Black),
                contentAlignment = Alignment.Center
            ) {
                if (vm.videoUri == null) {
                    EmptyState(onOpenVideo)
                } else {
                    AndroidView(
                        factory = { c ->
                            PlayerView(c).apply {
                                useController = false
                                resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                                player = vm.player
                                subtitleView?.visibility = android.view.View.GONE
                            }
                        },
                        modifier = Modifier.fillMaxSize()
                    )
                    // tap anywhere on the picture = play / pause
                    Box(
                        Modifier.matchParentSize().clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null
                        ) { vm.togglePlay() }
                    )
                    if (vm.showSubs) {
                        val idx = if (!vm.playing && vm.selCue >= 0) vm.selCue else vm.currentCue
                        Column(
                            Modifier.align(Alignment.BottomCenter).padding(horizontal = 12.dp, vertical = 14.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            if (idx >= 0 && idx < vm.cues.size) {
                                SubtitleLine(vm, idx)
                                if (!vm.playing) {
                                    Text(
                                        if (vm.phraseMode) "Tap the last word of the phrase"
                                        else "Tap a word · long-press to select a phrase",
                                        color = Color.White.copy(alpha = 0.75f), fontSize = 12.sp,
                                        modifier = Modifier.padding(top = 4.dp)
                                    )
                                }
                            }
                        }
                    }
                    if (!vm.playing && vm.task == null) {
                        Surface(
                            shape = CircleShape, color = Color.Black.copy(alpha = 0.45f),
                            modifier = Modifier.align(Alignment.Center).size(64.dp)
                                .clickable { vm.togglePlay() }
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Play, "Play", tint = Color.White, modifier = Modifier.size(38.dp))
                            }
                        }
                    }
                    if (fullscreen) {
                        IconButton(
                            onClick = onToggleFullscreen,
                            modifier = Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(6.dp),
                            colors = IconButtonDefaults.iconButtonColors(containerColor = Color.Black.copy(alpha = 0.4f))
                        ) { Icon(Icons.Close, "Exit full screen", tint = Color.White) }
                    }
                }
            }

            vm.task?.let { TaskCard(vm) }

            if (!fullscreen && vm.videoUri != null) {
                ControlPanel(vm, onToggleFullscreen, onLoadSrt)
            }
        }

        SnackbarHost(snack, Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 8.dp))
    }

    when (val s = vm.sheet) {
        is Sheet.Word -> WordSheet(vm, s)
        is Sheet.Phrase -> PhraseSheet(vm, s)
        Sheet.Generate -> GenerateSheet(vm)
        Sheet.Export -> ExportDialog(vm)
        null -> {}
    }
}

@Composable
private fun TopBar(vm: AppViewModel, onOpenVideo: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().statusBarsPadding().padding(start = 16.dp, end = 4.dp, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(Modifier.weight(1f)) {
            Text("SubPlayer", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            if (vm.videoName.isNotEmpty()) {
                Text(
                    vm.videoName + if (vm.cueInfo.isNotEmpty()) "  ·  ${vm.cueInfo}" else "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1, overflow = TextOverflow.Ellipsis
                )
            }
        }
        IconButton(onClick = onOpenVideo) { Icon(Icons.Folder, "Open video") }
    }
}

@Composable
private fun EmptyState(onOpenVideo: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
        Icon(Icons.Movie, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(56.dp))
        Spacer(Modifier.height(12.dp))
        Text("Learn German with your videos", style = MaterialTheme.typography.titleMedium, color = Color.White)
        Text(
            "Make subtitles offline, tap any word for its meaning, loop hard parts.",
            color = Color.White.copy(alpha = 0.7f), textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 6.dp, bottom = 16.dp)
        )
        FilledTonalButton(onClick = onOpenVideo) {
            Icon(Icons.Folder, null, Modifier.size(18.dp)); Spacer(Modifier.width(8.dp)); Text("Open a video")
        }
    }
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalFoundationApi::class)
@Composable
private fun SubtitleLine(vm: AppViewModel, cueIndex: Int) {
    val words = vm.tokens(vm.cues[cueIndex].text)
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(1.dp, Alignment.CenterHorizontally),
        modifier = Modifier
            .widthIn(max = 720.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(Color.Black.copy(alpha = 0.62f))
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        words.forEachIndexed { i, w ->
            val selected = vm.selCue == cueIndex && vm.selStart >= 0 &&
                i in minOf(vm.selStart, vm.selEnd)..maxOf(vm.selStart, vm.selEnd)
            Text(
                w,
                color = if (selected) Color.Black else Color.White,
                fontSize = 21.sp,
                fontWeight = FontWeight.Medium,
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(if (selected) MaterialTheme.colorScheme.secondary else Color.Transparent)
                    .combinedClickable(
                        onClick = { vm.onWordTap(cueIndex, i) },
                        onLongClick = { vm.onWordLongPress(cueIndex, i) },
                        onDoubleClick = { vm.selectWholeLine(cueIndex) }
                    )
                    .padding(horizontal = 3.dp, vertical = 2.dp)
            )
        }
    }
}

@Composable
private fun TaskCard(vm: AppViewModel) {
    val t = vm.task ?: return
    Surface(color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(t.title, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onPrimaryContainer)
                    Text(t.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
                }
                TextButton(onClick = { vm.cancelTask() }) { Text("Cancel") }
            }
            if (t.progress < 0) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 4.dp))
            else LinearProgressIndicator(progress = { t.progress / 100f }, modifier = Modifier.fillMaxWidth().padding(top = 4.dp))
        }
    }
}

@Composable
private fun ControlPanel(vm: AppViewModel, onToggleFullscreen: () -> Unit, onLoadSrt: () -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceContainer,
        shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.navigationBarsPadding().padding(horizontal = 14.dp, vertical = 8.dp)) {
            // seek bar
            var dragging by remember { mutableStateOf(false) }
            var dragValue by remember { mutableFloatStateOf(0f) }
            val dur = vm.duration.coerceAtLeast(1)
            Slider(
                value = if (dragging) dragValue else (vm.position.toFloat() / dur).coerceIn(0f, 1f),
                onValueChange = { dragging = true; dragValue = it },
                onValueChangeFinished = { vm.seekTo((dragValue * dur).toLong()); dragging = false },
                colors = SliderDefaults.colors(activeTrackColor = MaterialTheme.colorScheme.primary),
                modifier = Modifier.height(30.dp)
            )
            Row(Modifier.fillMaxWidth()) {
                Text(fmt(if (dragging) (dragValue * dur).toLong() else vm.position), style = MaterialTheme.typography.labelSmall)
                Spacer(Modifier.weight(1f))
                if (vm.pointA >= 0) {
                    Text(
                        if (vm.pointB > vm.pointA) "Repeat ${fmt(vm.pointA)} → ${fmt(vm.pointB)}" else "A ${fmt(vm.pointA)} · set B",
                        style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.secondary
                    )
                    Spacer(Modifier.weight(1f))
                }
                Text(fmt(vm.duration), style = MaterialTheme.typography.labelSmall)
            }

            // transport
            Row(
                Modifier.fillMaxWidth().padding(vertical = 2.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = { vm.prevLine() }) { Icon(Icons.Prev, "Previous line") }
                IconButton(onClick = { vm.skip(-5000) }) { Icon(Icons.Rewind, "Back 5 s") }
                FilledIconButton(onClick = { vm.togglePlay() }, modifier = Modifier.size(58.dp)) {
                    Icon(if (vm.playing) Icons.Pause else Icons.Play, "Play/Pause", Modifier.size(32.dp))
                }
                IconButton(onClick = { vm.skip(5000) }) { Icon(Icons.Forward, "Forward 5 s") }
                IconButton(onClick = { vm.nextLine() }) { Icon(Icons.Next, "Next line") }
            }

            // repeat + speed
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                FilterChip(selected = vm.pointA >= 0, onClick = { vm.setA() }, label = { Text("A") })
                FilterChip(selected = vm.pointB > vm.pointA && vm.pointA >= 0, onClick = { vm.setB() }, label = { Text("B") })
                AssistChip(onClick = { vm.loopLine() }, label = { Text("Loop line") },
                    leadingIcon = { Icon(Icons.Repeat, null, Modifier.size(16.dp)) })
                if (vm.pointA >= 0) {
                    IconButton(onClick = { vm.clearAB() }, modifier = Modifier.size(32.dp)) {
                        Icon(Icons.Close, "Repeat off", Modifier.size(18.dp))
                    }
                }
                Spacer(Modifier.weight(1f))
                AssistChip(
                    onClick = { vm.cycleSpeed() },
                    label = { Text(speedLabel(vm.speed)) },
                    colors = AssistChipDefaults.assistChipColors(
                        labelColor = if (vm.speed < 1f) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurface
                    )
                )
            }

            // actions
            Row(
                Modifier.fillMaxWidth().padding(top = 2.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                ActionButton(Icons.Subtitles, "Subtitles") { vm.sheet = Sheet.Generate }
                ActionButton(Icons.FileOpen, "Load .srt", onLoadSrt)
                ActionButton(Icons.Download, "Save clip") {
                    if (vm.pointA >= 0 && vm.pointB > vm.pointA) vm.sheet = Sheet.Export
                    else vm.message = "Set A and B first, then save the clip"
                }
                ActionButton(Icons.Subtitles, if (vm.showSubs) "Hide subs" else "Show subs", dim = !vm.showSubs) {
                    vm.showSubs = !vm.showSubs
                }
                ActionButton(Icons.Fullscreen, "Full screen", onClick = onToggleFullscreen)
            }
        }
    }
}

@Composable
private fun ActionButton(icon: ImageVector, label: String, dim: Boolean = false, onClick: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.clip(RoundedCornerShape(12.dp)).clickable(onClick = onClick).padding(horizontal = 6.dp, vertical = 6.dp)
    ) {
        Icon(icon, null, tint = if (dim) MaterialTheme.colorScheme.outline else MaterialTheme.colorScheme.primary)
        Text(label, style = MaterialTheme.typography.labelSmall, maxLines = 1)
    }
}

private fun speedLabel(s: Float) = when (s) { 0.75f -> "0.75×"; 0.5f -> "0.5×"; else -> "1×" }

fun fmt(ms: Long): String {
    val s = (ms.coerceAtLeast(0) / 1000)
    return if (s >= 3600) String.format(Locale.US, "%d:%02d:%02d", s / 3600, (s / 60) % 60, s % 60)
    else String.format(Locale.US, "%d:%02d", s / 60, s % 60)
}
