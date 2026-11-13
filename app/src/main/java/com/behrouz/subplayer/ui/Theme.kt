package com.behrouz.subplayer.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.runtime.getValue
import androidx.compose.animation.core.animateFloat
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width

private val Scheme = darkColorScheme(
    primary = Color(0xFFA996FF),
    onPrimary = Color(0xFF21105F),
    primaryContainer = Color(0xFF3B2C8C),
    onPrimaryContainer = Color(0xFFE6DEFF),
    secondary = Color(0xFFFFD54F),
    onSecondary = Color(0xFF3A2E00),
    secondaryContainer = Color(0xFF4A3F12),
    onSecondaryContainer = Color(0xFFFFE9A6),
    tertiary = Color(0xFF22E4FF),
    background = Color(0xFF06050C),
    surface = Color(0xFF15151C),
    surfaceVariant = Color(0xFF26252F),
    onSurface = Color(0xFFE7E5EE),
    onSurfaceVariant = Color(0xFFC6C3D2),
    surfaceContainer = Color(0xFF1C1B24),
    surfaceContainerHigh = Color(0xFF24232D),
    outline = Color(0xFF8F8C9C)
)

@Composable
fun SubPlayerTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Scheme, content = content)
}

/** Material icons (Apache 2.0) as path data, so no large icon library is needed. */
object Icons {
    private fun icon(name: String, vararg paths: String): ImageVector {
        val b = ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f)
        for (p in paths) b.addPath(addPathNodes(p), fill = SolidColor(Color.Black))
        return b.build()
    }

    val Play = icon("play", "M8,5v14l11,-7z")
    val Pause = icon("pause", "M6,19h4V5H6v14zM14,5v14h4V5h-4z")
    val Rewind = icon("rewind", "M11,18V6l-8.5,6 8.5,6zM11.5,12l8.5,6V6l-8.5,6z")
    val Forward = icon("forward", "M4,18l8.5,-6L4,6v12zM13,6v12l8.5,-6L13,6z")
    val Prev = icon("prev", "M6,6h2v12H6zM9.5,12l8.5,6V6z")
    val Next = icon("next", "M6,18l8.5,-6L6,6v12zM16,6v12h2V6h-2z")
    val Repeat = icon("repeat", "M7,7h10v3l4,-4 -4,-4v3H5v6h2V7zM17,17H7v-3l-4,4 4,4v-3h12v-6h-2v4z")
    val Subtitles = icon("subs", "M20,4H4c-1.1,0 -2,0.9 -2,2v12c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V6c0,-1.1 -0.9,-2 -2,-2zM4,12h4v2H4v-2zM14,18H4v-2h10v2zM20,18h-4v-2h4v2zM20,14H10v-2h10v2z")
    val Download = icon("download", "M19,9h-4V3H9v6H5l7,7 7,-7zM5,18v2h14v-2H5z")
    val Folder = icon("folder", "M20,6h-8l-2,-2H4c-1.1,0 -1.99,0.9 -1.99,2L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V8c0,-1.1 -0.9,-2 -2,-2zM20,18H4V8h16v10z")
    val Volume = icon("volume", "M3,9v6h4l5,5V4L7,9H3zM16.5,12c0,-1.77 -1.02,-3.29 -2.5,-4.03v8.05c1.48,-0.73 2.5,-2.25 2.5,-4.02zM14,3.23v2.06c2.89,0.86 5,3.54 5,6.71s-2.11,5.85 -5,6.71v2.06c4.01,-0.91 7,-4.49 7,-8.77s-2.99,-7.86 -7,-8.77z")
    val OpenIn = icon("open", "M19,19H5V5h7V3H5c-1.11,0 -2,0.9 -2,2v14c0,1.1 0.89,2 2,2h14c1.1,0 2,-0.9 2,-2v-7h-2v7zM14,3v2h3.59l-9.83,9.83 1.41,1.41L19,6.41V10h2V3h-7z")
    val Close = icon("close", "M19,6.41L17.59,5 12,10.59 6.41,5 5,6.41 10.59,12 5,17.59 6.41,19 12,13.41 17.59,19 19,17.59 13.41,12z")
    val Fullscreen = icon("full", "M7,14H5v5h5v-2H7v-3zM5,10h2V7h3V5H5v5zM17,17h-3v2h5v-5h-2v3zM14,5v2h3v3h2V5h-5z")
    val FileOpen = icon("file", "M14,2H6c-1.1,0 -1.99,0.9 -1.99,2L4,20c0,1.1 0.89,2 1.99,2H18c1.1,0 2,-0.9 2,-2V8l-6,-6zM16,18H8v-2h8v2zM16,14H8v-2h8v2zM13,9V3.5L18.5,9H13z")
    val Help = icon("help", "M11,18h2v-2h-2v2zM12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2zM12,20c-4.41,0 -8,-3.59 -8,-8s3.59,-8 8,-8 8,3.59 8,8 -3.59,8 -8,8zM12,6c-2.21,0 -4,1.79 -4,4h2c0,-1.1 0.9,-2 2,-2s2,0.9 2,2c0,2 -3,1.75 -3,5h2c0,-2.25 3,-2.5 3,-5 0,-2.21 -1.79,-4 -4,-4z")
    val Star = icon("star", "M12,17.27L18.18,21l-1.64,-7.03L22,9.24l-7.19,-0.61L12,2 9.19,8.63 2,9.24l5.46,4.73L5.82,21z")
    val StarOutline = icon("star_o", "M22,9.24l-7.19,-0.62L12,2 9.19,8.63 2,9.24l5.46,4.73L5.82,21 12,17.27 18.18,21l-1.63,-7.03L22,9.24zM12,15.4l-3.76,2.27 1,-4.28 -3.32,-2.88 4.38,-0.38L12,6.1l1.71,4.04 4.38,0.38 -3.32,2.88 1,4.28L12,15.4z")
    val More = icon("more", "M12,8c1.1,0 2,-0.9 2,-2s-0.9,-2 -2,-2 -2,0.9 -2,2 0.9,2 2,2zM12,10c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 2,-0.9 2,-2 -0.9,-2 -2,-2zM12,16c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 2,-0.9 2,-2 -0.9,-2 -2,-2z")
    val Bell = icon("bell", "M12,22c1.1,0 2,-0.9 2,-2h-4c0,1.1 0.89,2 2,2zM18,16v-5c0,-3.07 -1.64,-5.64 -4.5,-6.32V4c0,-0.83 -0.67,-1.5 -1.5,-1.5s-1.5,0.67 -1.5,1.5v0.68C7.63,5.36 6,7.92 6,11v5l-2,2v1h16v-1l-2,-2z")
    val Delete = icon("delete", "M6,19c0,1.1 0.9,2 2,2h8c1.1,0 2,-0.9 2,-2V7H6v12zM19,4h-3.5l-1,-1h-5l-1,1H5v2h14V4z")
    val Copy = icon("copy", "M16,1H4c-1.1,0 -2,0.9 -2,2v14h2V3h12V1zM19,5H8c-1.1,0 -2,0.9 -2,2v14c0,1.1 0.9,2 2,2h11c1.1,0 2,-0.9 2,-2V7c0,-1.1 -0.9,-2 -2,-2zM19,21H8V7h11v14z")
    val Share = icon("share", "M18,16.08c-0.76,0 -1.44,0.3 -1.96,0.77L8.91,12.7c0.05,-0.23 0.09,-0.46 0.09,-0.7s-0.04,-0.47 -0.09,-0.7l7.05,-4.11c0.54,0.5 1.25,0.81 2.04,0.81 1.66,0 3,-1.34 3,-3s-1.34,-3 -3,-3 -3,1.34 -3,3c0,0.24 0.04,0.47 0.09,0.7L8.04,9.81C7.5,9.31 6.79,9 6,9c-1.66,0 -3,1.34 -3,3s1.34,3 3,3c0.79,0 1.5,-0.31 2.04,-0.81l7.12,4.16c-0.05,0.21 -0.08,0.43 -0.08,0.65 0,1.61 1.31,2.92 2.92,2.92 1.61,0 2.92,-1.31 2.92,-2.92s-1.31,-2.92 -2.92,-2.92z")
    val Lock = icon("lock", "M18,8h-1V6c0,-2.76 -2.24,-5 -5,-5S7,3.24 7,6v2H6c-1.1,0 -2,0.9 -2,2v10c0,1.1 0.9,2 2,2h12c1.1,0 2,-0.9 2,-2V10c0,-1.1 -0.9,-2 -2,-2zM12,17c-1.1,0 -2,-0.9 -2,-2s0.9,-2 2,-2 2,0.9 2,2 -0.9,2 -2,2zM15.1,8H8.9V6c0,-1.71 1.39,-3.1 3.1,-3.1 1.71,0 3.1,1.39 3.1,3.1v2z")
    val School = icon("school", "M5,13.18v4L12,21l7,-3.82v-4L12,17l-7,-3.82zM12,3L1,9l11,6 9,-4.91V17h2V9L12,3z")
    val Check = icon("check", "M9,16.17L4.83,12l-1.42,1.41L9,19 21,7l-1.41,-1.41z")
    val Replay = icon("replay", "M12,5V1L7,6l5,5V7c3.31,0 6,2.69 6,6s-2.69,6 -6,6 -6,-2.69 -6,-6H4c0,4.42 3.58,8 8,8s8,-3.58 8,-8 -3.58,-8 -8,-8z")
    val Back = icon("back", "M20,11H7.83l5.59,-5.59L12,4l-8,8 8,8 1.41,-1.41L7.83,13H20v-2z")
    val FullscreenExit = icon("full_exit", "M5,16h3v3h2v-5L5,14v2zM8,8L5,8v2h5L10,5L8,5v3zM14,19h2v-3h3v-2h-5v5zM16,8L16,5h-2v5h5L19,8h-3z")
    val History = icon("history", "M13,3c-4.97,0 -9,4.03 -9,9H1l3.89,3.89 0.07,0.14L9,12H6c0,-3.87 3.13,-7 7,-7s7,3.13 7,7 -3.13,7 -7,7c-1.93,0 -3.68,-0.79 -4.94,-2.06l-1.42,1.42C8.27,19.99 10.51,21 13,21c4.97,0 9,-4.03 9,-9s-4.03,-9 -9,-9zM12,8v5l4.28,2.54 0.72,-1.21 -3.5,-2.08V8H12z")
    val Movie = icon("movie", "M18,4l2,4h-3l-2,-4h-2l2,4h-3l-2,-4H8l2,4H7L5,4H4c-1.1,0 -1.99,0.9 -1.99,2L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V4h-4z")
}


// ============================================================ visual system

/** The neon palette used for accents and gradients. */
object Neon {
    val Violet = Color(0xFF8B5CFF)
    val Cyan = Color(0xFF22E4FF)
    val Pink = Color(0xFFFF4FD8)
    val Gold = Color(0xFFFFD54F)
    val Deep = Color(0xFF06050C)
    val brush get() = androidx.compose.ui.graphics.Brush.linearGradient(listOf(Violet, Cyan))
    val hot get() = androidx.compose.ui.graphics.Brush.linearGradient(listOf(Pink, Violet, Cyan))
}

/** Slowly drifting aurora behind everything. */
@Composable
fun Aurora(modifier: androidx.compose.ui.Modifier = androidx.compose.ui.Modifier) {
    val t = androidx.compose.animation.core.rememberInfiniteTransition(label = "aurora")
    val a by t.animateFloat(0f, 1f, androidx.compose.animation.core.infiniteRepeatable(
        androidx.compose.animation.core.tween(18000, easing = androidx.compose.animation.core.LinearEasing),
        androidx.compose.animation.core.RepeatMode.Reverse), label = "a")
    val b by t.animateFloat(0f, 1f, androidx.compose.animation.core.infiniteRepeatable(
        androidx.compose.animation.core.tween(26000, easing = androidx.compose.animation.core.LinearEasing),
        androidx.compose.animation.core.RepeatMode.Reverse), label = "b")
    androidx.compose.foundation.Canvas(modifier.background(Neon.Deep)) {
        val w = size.width; val h = size.height; val r = maxOf(w, h)
        fun blob(cx: Float, cy: Float, color: Color, radius: Float) = drawCircle(
            androidx.compose.ui.graphics.Brush.radialGradient(listOf(color, Color.Transparent),
                center = androidx.compose.ui.geometry.Offset(cx, cy), radius = radius),
            radius = radius, center = androidx.compose.ui.geometry.Offset(cx, cy))
        blob(w * (0.15f + 0.5f * a), h * 0.12f, Neon.Violet.copy(alpha = 0.42f), r * 0.65f)
        blob(w * (0.95f - 0.6f * b), h * (0.45f + 0.2f * a), Neon.Cyan.copy(alpha = 0.22f), r * 0.55f)
        blob(w * (0.3f + 0.4f * b), h * (0.95f - 0.15f * b), Neon.Pink.copy(alpha = 0.24f), r * 0.6f)
    }
}


/** Frosted-glass panel: translucent fill + light gradient edge. */
fun androidx.compose.ui.Modifier.glass(
    shape: androidx.compose.ui.graphics.Shape = androidx.compose.foundation.shape.RoundedCornerShape(24.dp),
    alpha: Float = 0.07f
) = this
    .clip(shape)
    .background(Color.White.copy(alpha = alpha), shape)
    .border(1.dp, androidx.compose.ui.graphics.Brush.linearGradient(
        listOf(Color.White.copy(alpha = 0.28f), Color.White.copy(alpha = 0.04f), Neon.Cyan.copy(alpha = 0.18f))), shape)

/** Primary call-to-action: glowing violet→cyan pill. */
@Composable
fun GlowButton(text: String, modifier: androidx.compose.ui.Modifier = androidx.compose.ui.Modifier,
               icon: ImageVector? = null, enabled: Boolean = true, onClick: () -> Unit) {
    val shape = androidx.compose.foundation.shape.RoundedCornerShape(50)
    androidx.compose.foundation.layout.Box(
        modifier
            .shadow(if (enabled) 18.dp else 0.dp, shape, ambientColor = Neon.Cyan, spotColor = Neon.Violet)
            .clip(shape)
            .background(brush = if (enabled) Neon.brush else
                androidx.compose.ui.graphics.SolidColor(Color.White.copy(alpha = 0.12f)), shape = shape)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 22.dp, vertical = 13.dp),
        contentAlignment = androidx.compose.ui.Alignment.Center
    ) {
        androidx.compose.foundation.layout.Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            if (icon != null) {
                androidx.compose.material3.Icon(icon, null, tint = Color(0xFF0B0A1A), modifier = androidx.compose.ui.Modifier.size(20.dp))
                androidx.compose.foundation.layout.Spacer(androidx.compose.ui.Modifier.width(8.dp))
            }
            androidx.compose.material3.Text(text, color = Color(0xFF0B0A1A),
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold, fontSize = 16.sp)
        }
    }
}

/** Gradient headline text. */
@Composable
fun NeonTitle(text: String, size: androidx.compose.ui.unit.TextUnit = 26.sp, modifier: androidx.compose.ui.Modifier = androidx.compose.ui.Modifier) {
    androidx.compose.material3.Text(
        text, modifier = modifier,
        style = androidx.compose.ui.text.TextStyle(brush = Neon.hot, fontSize = size,
            fontWeight = androidx.compose.ui.text.font.FontWeight.Black, letterSpacing = (-0.5).sp)
    )
}

/** Small explanation line used under headings throughout the app. */
@Composable
fun Explain(text: String, modifier: androidx.compose.ui.Modifier = androidx.compose.ui.Modifier) {
    androidx.compose.material3.Text(text, modifier = modifier, color = Color.White.copy(alpha = 0.62f),
        fontSize = 13.sp, lineHeight = 18.sp)
}
