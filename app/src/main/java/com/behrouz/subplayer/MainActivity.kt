package com.behrouz.subplayer

import android.Manifest
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalConfiguration
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.common.util.UnstableApi
import com.behrouz.subplayer.ui.LockScreen
import com.behrouz.subplayer.ui.PlayerScreen
import com.behrouz.subplayer.ui.SubPlayerTheme
import com.behrouz.subplayer.words.Reminder

@androidx.annotation.OptIn(UnstableApi::class)
class MainActivity : ComponentActivity() {

    private val vm: AppViewModel by viewModels()
    private var fullscreenRequested by mutableStateOf(false)

    private val pickVideo = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) { keep(uri); vm.openVideo(uri) }
    }
    private val pickSrt = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) vm.loadSrt(uri)
    }
    private val notifyPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        val p = vm.pendingReminder
        vm.pendingReminder = null
        if (p != null) {
            if (granted) vm.setReminder(p.first, p.second)
            else vm.message = "Notifications are off for SubPlayer — allow them in Android settings to get reminders"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        Reminder.channel(this)
        setContent {
            SubPlayerTheme {
                if (vm.trialEnded || vm.showActivation) LockScreen(vm) else MainContent()
            }
        }
        if (savedInstanceState == null) handleIntent(intent)
    }

    @androidx.compose.runtime.Composable
    private fun MainContent() {
                // Turning the phone sideways = full screen, automatically.
                val landscape = LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE
                val fullscreen = (fullscreenRequested || landscape) && vm.videoUri != null && vm.screen == Screen.PLAYER
                LaunchedEffect(fullscreen) { applySystemBars(fullscreen) }
                LaunchedEffect(vm.pendingReminder) {
                    if (vm.pendingReminder != null && Build.VERSION.SDK_INT >= 33) notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
                BackHandler(enabled = fullscreen) { exitFullscreen() }
                PlayerScreen(
                    vm = vm,
                    fullscreen = fullscreen,
                    onToggleFullscreen = { if (fullscreen) exitFullscreen() else enterFullscreen() },
                    onOpenVideo = { pickVideo.launch(arrayOf("video/*")) },
                    onLoadSrt = { pickSrt.launch(arrayOf("*/*")) }
                )
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(i: Intent?) {
        if (i == null) return
        if (i.action == Intent.ACTION_VIEW) i.data?.let { vm.openVideo(it) }
        if (i.getStringExtra("open") == "review" && !vm.trialEnded) vm.startReview()
    }

    private fun enterFullscreen() {
        fullscreenRequested = true
        vm.touch()
        val size = vm.player.videoSize
        // landscape videos rotate the screen; portrait videos stay upright
        requestedOrientation = if (size.width >= size.height) ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                               else ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
    }

    private fun exitFullscreen() {
        fullscreenRequested = false
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        // give rotation back to the user after the screen has turned upright
        window.decorView.postDelayed({ requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED }, 1500)
    }

    private fun applySystemBars(hide: Boolean) {
        val c = WindowCompat.getInsetsController(window, window.decorView)
        if (hide) {
            c.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            c.hide(WindowInsetsCompat.Type.systemBars())
        } else {
            c.show(WindowInsetsCompat.Type.systemBars())
        }
    }

    override fun onResume() {
        super.onResume()
        vm.recheckTrial()
    }

    override fun onStop() {
        super.onStop()
        vm.rememberPosition()
        vm.player.pause()
    }

    private fun keep(uri: Uri) {
        try {
            contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        } catch (_: Exception) { }
    }
}
