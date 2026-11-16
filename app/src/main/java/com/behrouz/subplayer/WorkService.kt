package com.behrouz.subplayer

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat

/**
 * Keeps SubPlayer working while you are in another app or the screen is off: a download, transcribing a video or translating
 * all its lines. Android stops the network and the processor of apps in the background; a foreground service (with its
 * notification "SubPlayer · Downloading … 42 %") keeps them going. Runs only while such a task runs.
 */
class WorkService : Service() {

    companion object {
        private const val CHANNEL = "work"
        private const val ID = 4711
        private var running = false

        /** Starts (or updates) the notification. Safe to call often. */
        fun show(ctx: Context, title: String, text: String, percent: Int) {
            if (BuildConfig.PLAY) return                       // not in the Google Play version (see src/play/AndroidManifest.xml)
            val i = Intent(ctx, WorkService::class.java).putExtra("title", title).putExtra("text", text).putExtra("p", percent)
            runCatching {
                if (!running) ContextCompat.startForegroundService(ctx, i) else ctx.startService(i)
                running = true
            }
        }

        fun stop(ctx: Context) {
            if (!running) return
            running = false
            runCatching { ctx.stopService(Intent(ctx, WorkService::class.java)) }
        }
    }

    private var wake: PowerManager.WakeLock? = null
    private var wifi: WifiManager.WifiLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(CHANNEL) == null)
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Downloads and transcribing", NotificationManager.IMPORTANCE_LOW))
        val title = intent?.getStringExtra("title") ?: "SubPlayer"
        val text = intent?.getStringExtra("text") ?: ""
        val p = intent?.getIntExtra("p", -1) ?: -1
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_notify)
            .setContentTitle(title)
            .setContentText(text)
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .setSilent(true)
            .setContentIntent(open)
            .setProgress(100, p.coerceIn(0, 100), p < 0)
            .build()
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC) else startForeground(ID, n)
        } catch (e: Exception) {
            // Android 12+: not allowed to start from the background; the task still runs as long as Android lets it
            stopSelf(); return START_NOT_STICKY
        }
        if (wake == null) wake = (getSystemService(Context.POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "SubPlayer:work").apply { setReferenceCounted(false); acquire(4 * 60 * 60 * 1000L) }
        if (wifi == null) wifi = (applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager)
            .createWifiLock(if (Build.VERSION.SDK_INT >= 29) WifiManager.WIFI_MODE_FULL_HIGH_PERF else @Suppress("DEPRECATION") WifiManager.WIFI_MODE_FULL, "SubPlayer:work")
            .apply { setReferenceCounted(false); acquire() }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        runCatching { wake?.release() }
        runCatching { wifi?.release() }
        wake = null; wifi = null
        running = false
        super.onDestroy()
    }

    // the user swiped SubPlayer away from the recent apps: the task ends with the app
    override fun onTaskRemoved(rootIntent: Intent?) { stopSelf(); super.onTaskRemoved(rootIntent) }
}
