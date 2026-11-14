package com.behrouz.subplayer.asr

import android.content.Context
import android.net.Uri
import com.behrouz.subplayer.subs.Cue
import java.io.File

/**
 * Google Play build: Vosk is left out. Its prebuilt native library is not aligned for
 * 16 KB memory pages, which Google Play requires. Whisper and Online cover every use.
 */
object VoskEngine {
    const val AVAILABLE = false

    @Suppress("UNUSED_PARAMETER")
    suspend fun transcribe(ctx: Context, uri: Uri, modelDir: File, onProgress: (Int) -> Unit): List<Cue> =
        throw UnsupportedOperationException("The Fast engine is not part of this version — choose Accurate or Online")
}
