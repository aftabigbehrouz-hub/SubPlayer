package com.behrouz.subplayer.dict

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import java.util.Locale

/** Pronunciation: the phone's offline German voice, or a real recording from Wikimedia when online. */
class Speaker(ctx: Context) : TextToSpeech.OnInitListener {

    private val tts = TextToSpeech(ctx.applicationContext, this)
    private var player: MediaPlayer? = null

    @Volatile var germanVoice = false
        private set
    @Volatile var ready = false
        private set

    override fun onInit(status: Int) {
        ready = status == TextToSpeech.SUCCESS
        if (ready) {
            val r = tts.setLanguage(Locale.GERMANY)
            germanVoice = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED
        }
    }

    /** Returns false if no German voice is installed. */
    fun speak(text: String, slow: Boolean = false): Boolean {
        if (!ready || !germanVoice) return false
        tts.setSpeechRate(if (slow) 0.7f else 0.95f)
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "subplayer")
        return true
    }

    fun playRecording(url: String, onError: (String) -> Unit) {
        stopRecording()
        try {
            player = MediaPlayer().apply {
                setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build())
                setDataSource(url)
                setOnPreparedListener { it.start() }
                setOnCompletionListener { stopRecording() }
                setOnErrorListener { _, _, _ -> onError("Recording could not be played (offline?)"); stopRecording(); true }
                prepareAsync()
            }
        } catch (e: Exception) {
            onError("Recording could not be played: ${e.message}")
        }
    }

    private fun stopRecording() {
        player?.release()
        player = null
    }

    fun shutdown() {
        stopRecording()
        tts.shutdown()
    }
}
