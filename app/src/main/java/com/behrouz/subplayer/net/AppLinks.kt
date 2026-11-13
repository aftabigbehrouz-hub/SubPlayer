package com.behrouz.subplayer.net

import android.content.Context
import android.content.Intent

/** Sends a word or question to an installed app (ChatGPT, Grok, dict.cc, any dictionary). */
object AppLinks {
    const val CHATGPT = "com.openai.chatgpt"
    const val GROK = "ai.x.grok"
    val DICTCC = listOf("cc.dict.dictcc", "cc.dict.dictccplus")

    fun installed(ctx: Context, pkg: String) = try { ctx.packageManager.getPackageInfo(pkg, 0); true } catch (_: Exception) { false }

    /** Shares text into one app (e.g. a new ChatGPT / Grok chat, pre-filled). */
    fun sendText(ctx: Context, pkg: String?, text: String): Boolean = try {
        val i = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
        if (pkg != null) i.setPackage(pkg)
        ctx.startActivity((if (pkg == null) Intent.createChooser(i, "Send to…") else i).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        true
    } catch (_: Exception) { false }

    /** Android's "look up selected text" action — supported by dictionary and translation apps. */
    fun lookUp(ctx: Context, pkg: String?, word: String): Boolean = try {
        val i = Intent(Intent.ACTION_PROCESS_TEXT).setType("text/plain")
            .putExtra(Intent.EXTRA_PROCESS_TEXT, word).putExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, true)
        if (pkg != null) {
            i.setPackage(pkg)
            if (ctx.packageManager.queryIntentActivities(i, 0).isEmpty()) throw IllegalStateException()
            ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } else {
            if (ctx.packageManager.queryIntentActivities(i, 0).isEmpty()) throw IllegalStateException()
            ctx.startActivity(Intent.createChooser(i, "Look up in…").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        true
    } catch (_: Exception) { false }
}
