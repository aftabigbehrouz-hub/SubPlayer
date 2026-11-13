package com.behrouz.subplayer.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

private val Scheme = darkColorScheme(
    primary = Color(0xFFB4A7FF),
    onPrimary = Color(0xFF21105F),
    primaryContainer = Color(0xFF3B2C8C),
    onPrimaryContainer = Color(0xFFE6DEFF),
    secondary = Color(0xFFFFD54F),
    onSecondary = Color(0xFF3A2E00),
    secondaryContainer = Color(0xFF4A3F12),
    onSecondaryContainer = Color(0xFFFFE9A6),
    tertiary = Color(0xFF7FD8C8),
    background = Color(0xFF0E0E13),
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
    val Movie = icon("movie", "M18,4l2,4h-3l-2,-4h-2l2,4h-3l-2,-4H8l2,4H7L5,4H4c-1.1,0 -1.99,0.9 -1.99,2L2,18c0,1.1 0.9,2 2,2h16c1.1,0 2,-0.9 2,-2V4h-4z")
}
