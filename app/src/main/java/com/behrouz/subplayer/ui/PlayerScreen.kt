package com.behrouz.subplayer.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.behrouz.subplayer.AppViewModel
import com.behrouz.subplayer.Screen
import com.behrouz.subplayer.Sheet
import com.behrouz.subplayer.words.Recents
import java.util.Locale

private val White = Color.White
private val Ink = Color(0xFF0B0A1A)
private val Clear = Brush.linearGradient(listOf(Color.Transparent, Color.Transparent))

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
        vm.message?.let {
            val long = it.length > 60
            snack.showSnackbar(it, withDismissAction = long, duration = if (long) SnackbarDuration.Long else SnackbarDuration.Short)
            vm.message = null
        }
    }

    Box(Modifier.fillMaxSize()) {
        Aurora(Modifier.fillMaxSize())
        when {
            vm.screen == Screen.WORDS -> WordsScreen(vm)
            vm.screen == Screen.REVIEW -> ReviewScreen(vm)
            vm.screen == Screen.PRACTICE -> PracticeScreen(vm)
            fullscreen && vm.videoUri != null -> Box(Modifier.fillMaxSize().background(Color.Black)) {
                VideoSurface(vm, fullscreen = true, onToggleFullscreen = onToggleFullscreen, onOpenVideo = onOpenVideo)
            }
            else -> Column(Modifier.fillMaxSize()) {
                TopBar(vm, onOpenVideo)
                if (vm.videoUri == null) {
                    Home(vm, onOpenVideo, Modifier.weight(1f))
                } else {
                    Box(
                        Modifier.fillMaxWidth().weight(1f).padding(horizontal = 10.dp)
                            .clip(RoundedCornerShape(26.dp)).background(Color.Black)
                            .border(1.dp, Brush.linearGradient(listOf(Neon.Violet.copy(alpha = 0.6f), Neon.Cyan.copy(alpha = 0.4f))), RoundedCornerShape(26.dp))
                    ) {
                        VideoSurface(vm, fullscreen = false, onToggleFullscreen = onToggleFullscreen, onOpenVideo = onOpenVideo)
                    }
                }
                vm.task?.let { TaskCard(vm) }
                if (vm.videoUri != null) ControlPanel(vm, onToggleFullscreen, onLoadSrt)
            }
        }
        SnackbarHost(snack, Modifier.align(Alignment.BottomCenter).navigationBarsPadding().padding(bottom = 8.dp))
    }

    when (val s = vm.sheet) {
        is Sheet.Word -> WordSheet(vm, s)
        is Sheet.Phrase -> PhraseSheet(vm, s)
        Sheet.Generate -> GenerateSheet(vm)
        Sheet.Export -> ExportDialog(vm)
        Sheet.Help -> HelpSheet(vm)
        Sheet.Settings -> SettingsSheet(vm)
        Sheet.Videos -> VideosSheet(vm, onOpenVideo)
        Sheet.SubFile -> SubFileSheet(vm, onLoadSrt)
        is Sheet.Link -> LinkSheet(vm, s)
        is Sheet.AddSentences -> AddSentencesSheet(vm, s)
        null -> {}
    }
    if (vm.showTour) Tour(vm)
}

// ================================================================ top bar

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun TopBar(vm: AppViewModel, onOpenVideo: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().statusBarsPadding().padding(start = 18.dp, end = 6.dp, top = 6.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(Modifier.weight(1f)) {
            NeonTitle("SubPlayer", 24.sp)
            Text(
                if (vm.videoName.isNotEmpty()) vm.videoName + if (vm.cueInfo.isNotEmpty()) "  ·  ${vm.cueInfo}" else ""
                else "Watch · understand · remember",
                color = White.copy(alpha = 0.6f), fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis
            )
            if (vm.licence == null && vm.trialLeft > 0) {
                Text(
                    "Free trial · ${vm.trialLeft} day${if (vm.trialLeft == 1) "" else "s"} left — Buy",
                    color = if (vm.trialLeft <= 3) Neon.Pink else Neon.Gold, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 2.dp).clip(RoundedCornerShape(50))
                        .clickable { vm.showActivation = true }.padding(vertical = 2.dp)
                )
            }
        }
        BarIcon(Icons.Star, "My words", badge = vm.dueCount) { vm.screen = Screen.WORDS }
        BarIcon(Icons.Folder, "Open a video") { onOpenVideo() }
        BarIcon(Icons.History, "Recent videos") { vm.sheet = Sheet.Videos }
        BarIcon(Icons.Help, "How it works") { vm.sheet = Sheet.Help }
        BarIcon(Icons.More, "Settings") { vm.sheet = Sheet.Settings }
    }
}

@Composable
fun BarIcon(icon: ImageVector, label: String, badge: Int = 0, tint: Color = White, onClick: () -> Unit) {
    Box {
        IconButton(onClick = onClick) { Icon(icon, label, tint = tint) }
        if (badge > 0) {
            Box(
                Modifier.align(Alignment.TopEnd).offset(x = (-4).dp, y = 6.dp).size(18.dp).background(Neon.Pink, CircleShape),
                contentAlignment = Alignment.Center
            ) { Text(if (badge > 99) "99" else "$badge", color = White, fontSize = 10.sp, fontWeight = FontWeight.Bold) }
        }
    }
}

// =================================================================== home

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun Home(vm: AppViewModel, onOpenVideo: () -> Unit, modifier: Modifier) {
    Column(
        modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 18.dp).navigationBarsPadding(),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(Modifier.height(18.dp))
        Column(
            Modifier.fillMaxWidth().glass(RoundedCornerShape(30.dp)).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                Modifier.size(84.dp).shadow(30.dp, CircleShape, ambientColor = Neon.Cyan, spotColor = Neon.Violet)
                    .background(Neon.hot, CircleShape),
                contentAlignment = Alignment.Center
            ) { Icon(Icons.Play, null, tint = Ink, modifier = Modifier.size(44.dp)) }
            Spacer(Modifier.height(16.dp))
            Text("Learn German from what you love to watch", color = White, fontSize = 20.sp,
                fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
            Spacer(Modifier.height(6.dp))
            Explain("Open any video. SubPlayer writes the subtitles on your phone, explains every word you tap, " +
                "loops the hard parts and brings saved words back right before you'd forget them.",
                Modifier.padding(horizontal = 4.dp))
            Spacer(Modifier.height(18.dp))
            GlowButton("Open a video", icon = Icons.Folder, onClick = onOpenVideo)
            Spacer(Modifier.height(10.dp))
            Pill("Paste a video link (Tagesschau, .mp4 …)", icon = Icons.Download) { vm.openLinkSheet() }
        }

        if (vm.words.isNotEmpty()) {
            Spacer(Modifier.height(14.dp))
            Row(
                Modifier.fillMaxWidth().glass(RoundedCornerShape(22.dp)).clickable { vm.startReview() }.padding(18.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.School, null, tint = Neon.Gold, modifier = Modifier.size(30.dp))
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text(if (vm.dueCount > 0) "${vm.dueCount} words to review" else "All caught up",
                        color = White, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                    Explain("${vm.words.size} saved · tap to practise")
                }
                Icon(Icons.Next, null, tint = White.copy(alpha = 0.7f))
            }
        }

        if (vm.recentList.isNotEmpty()) {
            Text("CONTINUE WATCHING", color = Neon.Cyan, fontSize = 12.sp, letterSpacing = 1.5.sp,
                fontWeight = FontWeight.Bold, modifier = Modifier.fillMaxWidth().padding(top = 22.dp, bottom = 8.dp))
            vm.recentList.take(6).forEach { RecentRow(vm, it) }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
fun RecentRow(vm: AppViewModel, item: Recents.Item) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 4.dp).glass(RoundedCornerShape(18.dp))
            .clickable { vm.openRecent(item) }.padding(14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(Icons.Movie, null, tint = Neon.Violet)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(item.name, color = White, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Medium)
            if (item.durationMs > 0) {
                LinearProgressIndicator(
                    progress = { (item.positionMs.toFloat() / item.durationMs).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().padding(top = 6.dp).height(3.dp).clip(RoundedCornerShape(2.dp)),
                    color = Neon.Cyan, trackColor = White.copy(alpha = 0.12f)
                )
            }
        }
        Spacer(Modifier.width(10.dp))
        Text(if (item.positionMs > 3000) fmt(item.positionMs) else "Start", color = White.copy(alpha = 0.7f), fontSize = 12.sp)
    }
}

// ========================================================== video surface

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun BoxScope.VideoSurface(vm: AppViewModel, fullscreen: Boolean, onToggleFullscreen: () -> Unit, onOpenVideo: () -> Unit) {
    AndroidView(
        factory = { c ->
            PlayerView(c).apply {
                useController = false
                resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                player = vm.player
                subtitleView?.visibility = android.view.View.GONE
                setShutterBackgroundColor(android.graphics.Color.BLACK)
            }
        },
        onRelease = { it.player = null },
        modifier = Modifier.fillMaxSize()
    )
    // tap = play/pause (full screen: show/hide controls); double-tap left/right third = -5 s / +5 s
    Box(
        Modifier.matchParentSize().pointerInput(fullscreen) {
            detectTapGestures(
                onTap = {
                    if (fullscreen) { if (vm.controlsVisible) vm.controlsVisible = false else vm.touch() }
                    else vm.togglePlay()
                },
                onDoubleTap = { o ->
                    when {
                        o.x < size.width / 3f -> vm.skip(-5000)
                        o.x > size.width * 2f / 3f -> vm.skip(5000)
                        else -> vm.togglePlay()
                    }
                    vm.touch()
                }
            )
        }
    )

    val overlay = fullscreen && (vm.controlsVisible || !vm.playing)
    if (vm.showSubs) {
        val idx = when {
            !vm.playing && vm.selCue >= 0 -> vm.selCue
            vm.currentCue >= 0 -> vm.currentCue
            !vm.playing -> vm.heldCue          // "pause after each line": keep the finished line visible
            else -> -1
        }
        Column(
            Modifier.align(Alignment.BottomCenter)
                .padding(horizontal = 14.dp)
                .padding(bottom = if (overlay) 150.dp else if (fullscreen) 28.dp else 14.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            if (vm.shadowWaiting) {
                Text("🎙  Your turn — say it aloud", color = Neon.Gold, fontSize = 15.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(bottom = 6.dp).clip(RoundedCornerShape(50)).background(Color.Black.copy(alpha = 0.6f))
                        .padding(horizontal = 14.dp, vertical = 6.dp))
            }
            if (idx >= 0 && idx < vm.cues.size) {
                SubtitleLine(vm, idx, big = fullscreen)
                if (!vm.playing) {
                    Text(
                        if (vm.phraseMode) "Now tap the last word of the phrase"
                        else "Tap a word · long-press = phrase · double-tap = whole line",
                        color = White.copy(alpha = 0.7f), fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp)
                    )
                }
            }
        }
    }

    if (!fullscreen && !vm.playing && vm.task == null) {
        Box(
            Modifier.align(Alignment.Center).size(70.dp)
                .shadow(24.dp, CircleShape, ambientColor = Neon.Cyan, spotColor = Neon.Violet)
                .background(Color.Black.copy(alpha = 0.35f), CircleShape)
                .border(1.5.dp, Neon.brush, CircleShape)
                .clickable { vm.togglePlay() },
            contentAlignment = Alignment.Center
        ) { Icon(Icons.Play, "Play", tint = White, modifier = Modifier.size(40.dp)) }
    }

    if (fullscreen) {
        AnimatedVisibility(overlay, enter = fadeIn(), exit = fadeOut(), modifier = Modifier.matchParentSize()) {
            FullscreenControls(vm, onToggleFullscreen, onOpenVideo)
        }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun FullscreenControls(vm: AppViewModel, onExit: () -> Unit, onOpenVideo: () -> Unit) {
    Box(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().align(Alignment.TopCenter)
                .background(Brush.verticalGradient(listOf(Color.Black.copy(alpha = 0.75f), Color.Transparent)))
                .statusBarsPadding().padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onExit) { Icon(Icons.Back, "Exit full screen", tint = White) }
            Text(vm.videoName, color = White, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            BarIcon(Icons.Star, "My words", badge = vm.dueCount) { onExit(); vm.screen = Screen.WORDS }
            BarIcon(Icons.Folder, "Open another video") { onOpenVideo() }
            BarIcon(Icons.FullscreenExit, "Exit full screen") { onExit() }
        }
        Row(Modifier.align(Alignment.Center), verticalAlignment = Alignment.CenterVertically) {
            RoundGlass(Icons.Prev, 48.dp) { vm.prevLine(); vm.touch() }
            Spacer(Modifier.width(18.dp))
            RoundGlass(Icons.Rewind, 54.dp) { vm.skip(-5000); vm.touch() }
            Spacer(Modifier.width(22.dp))
            PlayOrb(vm, 76.dp)
            Spacer(Modifier.width(22.dp))
            RoundGlass(Icons.Forward, 54.dp) { vm.skip(5000); vm.touch() }
            Spacer(Modifier.width(18.dp))
            RoundGlass(Icons.Next, 48.dp) { vm.nextLine(); vm.touch() }
        }
        Column(
            Modifier.fillMaxWidth().align(Alignment.BottomCenter)
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.8f))))
                .navigationBarsPadding().padding(horizontal = 18.dp, vertical = 8.dp)
        ) {
            SeekBar(vm)
            RepeatRow(vm)
        }
    }
}

@Composable
private fun RoundGlass(icon: ImageVector, size: Dp, onClick: () -> Unit) {
    Box(Modifier.size(size).glass(CircleShape, 0.10f).clickable(onClick = onClick), contentAlignment = Alignment.Center) {
        Icon(icon, null, tint = White, modifier = Modifier.size(size * 0.5f))
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun PlayOrb(vm: AppViewModel, size: Dp) {
    Box(
        Modifier.size(size).shadow(26.dp, CircleShape, ambientColor = Neon.Cyan, spotColor = Neon.Violet)
            .background(Neon.brush, CircleShape).clickable { vm.togglePlay(); vm.touch() },
        contentAlignment = Alignment.Center
    ) {
        Icon(if (vm.playing) Icons.Pause else Icons.Play, "Play/Pause", tint = Ink, modifier = Modifier.size(size * 0.5f))
    }
}

// ============================================================== subtitles

@androidx.annotation.OptIn(UnstableApi::class)
@OptIn(ExperimentalLayoutApi::class, ExperimentalFoundationApi::class)
@Composable
private fun SubtitleLine(vm: AppViewModel, cueIndex: Int, big: Boolean) {
    val words = vm.tokens(vm.cues[cueIndex].text)
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(1.dp, Alignment.CenterHorizontally),
        modifier = Modifier
            .widthIn(max = 760.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(Color.Black.copy(alpha = 0.55f))
            .border(1.dp, Brush.linearGradient(listOf(White.copy(alpha = 0.25f), Color.Transparent, Neon.Cyan.copy(alpha = 0.25f))), RoundedCornerShape(16.dp))
            .padding(horizontal = 10.dp, vertical = 7.dp)
    ) {
        words.forEachIndexed { i, w ->
            val selected = vm.selCue == cueIndex && vm.selStart >= 0 &&
                i in minOf(vm.selStart, vm.selEnd)..maxOf(vm.selStart, vm.selEnd)
            val known = vm.isKnownWord(w)
            Text(
                w,
                color = when { selected -> Ink; known -> Neon.Gold; else -> White },
                fontSize = if (big) 24.sp else 21.sp,
                fontWeight = FontWeight.Medium,
                textDecoration = if (known && !selected) TextDecoration.Underline else null,
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (selected) Neon.brush else Clear)
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

// ================================================================ panels

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun TaskCard(vm: AppViewModel) {
    val t = vm.task ?: return
    Column(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 6.dp).glass(RoundedCornerShape(18.dp), 0.10f).padding(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(t.title, color = White, fontWeight = FontWeight.SemiBold)
                Text(t.message, color = White.copy(alpha = 0.7f), fontSize = 12.sp)
            }
            TextButton(onClick = { vm.cancelTask() }) { Text("Cancel", color = Neon.Pink) }
        }
        if (t.progress < 0) LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 6.dp), color = Neon.Cyan, trackColor = White.copy(alpha = 0.1f))
        else LinearProgressIndicator(progress = { t.progress / 100f }, modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
            color = Neon.Cyan, trackColor = White.copy(alpha = 0.1f))
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun SeekBar(vm: AppViewModel) {
    var dragging by remember { mutableStateOf(false) }
    var dragValue by remember { mutableFloatStateOf(0f) }
    val dur = vm.duration.coerceAtLeast(1)
    Slider(
        value = if (dragging) dragValue else (vm.position.toFloat() / dur).coerceIn(0f, 1f),
        onValueChange = { dragging = true; dragValue = it; vm.touch() },
        onValueChangeFinished = { vm.seekTo((dragValue * dur).toLong()); dragging = false },
        colors = SliderDefaults.colors(thumbColor = Neon.Cyan, activeTrackColor = Neon.Violet, inactiveTrackColor = White.copy(alpha = 0.15f)),
        modifier = Modifier.height(30.dp)
    )
    Row(Modifier.fillMaxWidth()) {
        Text(fmt(if (dragging) (dragValue * dur).toLong() else vm.position), color = White.copy(alpha = 0.8f), fontSize = 12.sp)
        Spacer(Modifier.weight(1f))
        if (vm.pointA >= 0) {
            Text(
                if (vm.pointB > vm.pointA) "⟲ ${fmt(vm.pointA)} → ${fmt(vm.pointB)}" else "A ${fmt(vm.pointA)} · now set B",
                color = Neon.Gold, fontSize = 12.sp
            )
            Spacer(Modifier.weight(1f))
        }
        Text(fmt(vm.duration), color = White.copy(alpha = 0.8f), fontSize = 12.sp)
    }
}

@Composable
fun Pill(text: String, active: Boolean = false, icon: ImageVector? = null, onClick: () -> Unit) {
    val shape = RoundedCornerShape(50)
    Row(
        Modifier.clip(shape)
            .background(if (active) Neon.brush else Brush.linearGradient(listOf(White.copy(alpha = 0.08f), White.copy(alpha = 0.05f))), shape)
            .border(1.dp, if (active) Clear else Brush.linearGradient(listOf(White.copy(alpha = 0.25f), White.copy(alpha = 0.06f))), shape)
            .clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (icon != null) { Icon(icon, null, tint = if (active) Ink else White, modifier = Modifier.size(16.dp)); Spacer(Modifier.width(6.dp)) }
        Text(text, color = if (active) Ink else White, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun RepeatRow(vm: AppViewModel) {
    Row(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Pill("A", active = vm.pointA >= 0) { vm.setA(); vm.touch() }
        Pill("B", active = vm.pointB > vm.pointA && vm.pointA >= 0) { vm.setB(); vm.touch() }
        Pill("Loop line", icon = Icons.Repeat) { vm.loopLine(); vm.touch() }
        if (vm.pointA >= 0) {
            Box(Modifier.size(34.dp).glass(CircleShape).clickable { vm.clearAB() }, contentAlignment = Alignment.Center) {
                Icon(Icons.Close, "Repeat off", tint = White, modifier = Modifier.size(16.dp))
            }
        }
        Spacer(Modifier.weight(1f))
        Pill(speedLabel(vm.speed), active = vm.speed < 1f) { vm.cycleSpeed(); vm.touch() }
    }
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun ControlPanel(vm: AppViewModel, onToggleFullscreen: () -> Unit, onLoadSrt: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(10.dp).navigationBarsPadding()
            .glass(RoundedCornerShape(28.dp)).padding(horizontal = 14.dp, vertical = 8.dp)
    ) {
        SeekBar(vm)
        Row(
            Modifier.fillMaxWidth().padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = { vm.prevLine() }) { Icon(Icons.Prev, "Previous line", tint = White) }
            IconButton(onClick = { vm.skip(-5000) }) { Icon(Icons.Rewind, "Back 5 s", tint = White) }
            PlayOrb(vm, 62.dp)
            IconButton(onClick = { vm.skip(5000) }) { Icon(Icons.Forward, "Forward 5 s", tint = White) }
            IconButton(onClick = { vm.nextLine() }) { Icon(Icons.Next, "Next line", tint = White) }
        }
        RepeatRow(vm)
        Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Pill("Pause each line", active = vm.autoPause) { vm.toggleAutoPause() }
            Pill("🎙 Shadowing", active = vm.shadowing) { vm.toggleShadowing() }
        }
        Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            ActionButton(Icons.Subtitles, "Subtitles") { vm.sheet = Sheet.Generate }
            ActionButton(Icons.FileOpen, "Subtitle file") { vm.sheet = Sheet.SubFile }
            ActionButton(Icons.Download, "Save clip") {
                if (vm.pointA >= 0 && vm.pointB > vm.pointA) vm.sheet = Sheet.Export
                else vm.message = "Set A and B first, then save the clip"
            }
            ActionButton(Icons.Subtitles, if (vm.showSubs) "Hide subs" else "Show subs", dim = !vm.showSubs) { vm.showSubs = !vm.showSubs }
            ActionButton(Icons.Fullscreen, "Full screen", onClick = onToggleFullscreen)
        }
    }
}

@Composable
private fun ActionButton(icon: ImageVector, label: String, dim: Boolean = false, onClick: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.clip(RoundedCornerShape(14.dp)).clickable(onClick = onClick).padding(horizontal = 6.dp, vertical = 6.dp)
    ) {
        Icon(icon, null, tint = if (dim) White.copy(alpha = 0.35f) else Neon.Cyan)
        Text(label, color = White.copy(alpha = 0.85f), fontSize = 11.sp, maxLines = 1)
    }
}

private fun speedLabel(s: Float) = when (s) { 0.75f -> "0.75×"; 0.5f -> "0.5×"; else -> "1×" }

fun fmt(ms: Long): String {
    val s = (ms.coerceAtLeast(0) / 1000)
    return if (s >= 3600) String.format(Locale.US, "%d:%02d:%02d", s / 3600, (s / 60) % 60, s % 60)
    else String.format(Locale.US, "%d:%02d", s / 60, s % 60)
}
