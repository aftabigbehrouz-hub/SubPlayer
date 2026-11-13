package com.behrouz.subplayer.words

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import com.behrouz.subplayer.MainActivity
import com.behrouz.subplayer.R
import java.util.Calendar
import java.util.concurrent.TimeUnit

/** Daily "words to review" notification at the hour the user picked. */
object Reminder {
    private const val WORK = "review-reminder"
    const val CHANNEL = "review"

    private fun prefs(ctx: Context) = ctx.getSharedPreferences("reminder", Context.MODE_PRIVATE)
    fun enabled(ctx: Context) = prefs(ctx).getBoolean("on", false)
    fun hour(ctx: Context) = prefs(ctx).getInt("hour", 20)

    fun set(ctx: Context, on: Boolean, hour: Int) {
        prefs(ctx).edit().putBoolean("on", on).putInt("hour", hour).apply()
        val wm = WorkManager.getInstance(ctx)
        if (!on) { wm.cancelUniqueWork(WORK); return }
        val now = Calendar.getInstance()
        val next = (now.clone() as Calendar).apply {
            set(Calendar.HOUR_OF_DAY, hour); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0)
            if (!after(now)) add(Calendar.DAY_OF_YEAR, 1)
        }
        val req = PeriodicWorkRequestBuilder<ReminderWorker>(24, TimeUnit.HOURS)
            .setInitialDelay(next.timeInMillis - now.timeInMillis, TimeUnit.MILLISECONDS)
            .build()
        wm.enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.UPDATE, req)
    }

    fun channel(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 26) {
            val nm = ctx.getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Word review", NotificationManager.IMPORTANCE_DEFAULT))
        }
    }

    fun canNotify(ctx: Context) = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    fun show(ctx: Context, due: Int) = notify(ctx, 7,
        if (due == 1) "1 word is waiting for you" else "$due words are waiting for you",
        "A few minutes of review keeps them in your memory.", open = "review")

    /** Schedules the two trial notifications (safe to call repeatedly). */
    fun scheduleTrial(ctx: Context, trialEnd: Long) {
        val wm = WorkManager.getInstance(ctx)
        val now = System.currentTimeMillis()
        fun at(name: String, time: Long, ended: Boolean) {
            if (time <= now) return
            val req = androidx.work.OneTimeWorkRequestBuilder<TrialWorker>()
                .setInitialDelay(time - now, TimeUnit.MILLISECONDS)
                .setInputData(androidx.work.workDataOf("ended" to ended))
                .build()
            wm.enqueueUniqueWork(name, androidx.work.ExistingWorkPolicy.KEEP, req)
        }
        at("trial-1day", trialEnd - 24L * 60 * 60 * 1000, false)
        at("trial-ended", trialEnd + 60_000, true)
    }

    fun notify(ctx: Context, id: Int, title: String, text: String, open: String? = null) {
        if (!canNotify(ctx)) return
        channel(ctx)
        val open = PendingIntent.getActivity(
            ctx, 1,
            Intent(ctx, MainActivity::class.java).apply { if (open != null) putExtra("open", open) }.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(R.drawable.ic_notify)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(ctx).notify(id, n)
        } catch (_: SecurityException) { }
    }
}

/** One-time notifications: one day before the trial ends, and when it has ended. */
class TrialWorker(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {
    override fun doWork(): Result {
        val c = applicationContext
        if (com.behrouz.subplayer.licence.Licence.current(c) != null) return Result.success()
        val ended = inputData.getBoolean("ended", false)
        Reminder.notify(
            c, 8,
            if (ended) "Your SubPlayer free trial has ended" else "1 day left in your SubPlayer trial",
            "To keep using it, send your device code to @${com.behrouz.subplayer.licence.Licence.SELLER_TELEGRAM} on Telegram."
        )
        return Result.success()
    }
}

class ReminderWorker(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {
    override fun doWork(): Result {
        val store = WordStore(applicationContext)
        val due = try { store.dueCount(System.currentTimeMillis()) } finally { store.close() }
        if (due > 0) Reminder.show(applicationContext, due)
        return Result.success()
    }
}
