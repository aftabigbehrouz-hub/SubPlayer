package com.behrouz.subplayer

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.common.util.UnstableApi
import com.behrouz.subplayer.ui.PlayerScreen
import com.behrouz.subplayer.ui.SubPlayerTheme

@androidx.annotation.OptIn(UnstableApi::class)
class MainActivity : ComponentActivity() {

    private val vm: AppViewModel by viewModels()
    private var fullscreen by mutableStateOf(false)

    private val pickVideo = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) { keep(uri); vm.openVideo(uri) }
    }
    private val pickSrt = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) vm.loadSrt(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            SubPlayerTheme {
                PlayerScreen(
                    vm = vm,
                    fullscreen = fullscreen,
                    onToggleFullscreen = { applyFullscreen(!fullscreen) },
                    onOpenVideo = { pickVideo.launch(arrayOf("video/*")) },
                    onLoadSrt = { pickSrt.launch(arrayOf("*/*")) }
                )
            }
        }
        if (savedInstanceState == null) handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(i: Intent?) {
        if (i?.action == Intent.ACTION_VIEW) i.data?.let { vm.openVideo(it) }
    }

    private fun applyFullscreen(on: Boolean) {
        fullscreen = on
        val c = WindowCompat.getInsetsController(window, window.decorView)
        if (on) {
            c.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            c.hide(WindowInsetsCompat.Type.systemBars())
        } else {
            c.show(WindowInsetsCompat.Type.systemBars())
        }
    }

    override fun onStop() {
        super.onStop()
        vm.player.pause()
    }

    private fun keep(uri: Uri) {
        try {
            contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (_: Exception) { }
    }
}
