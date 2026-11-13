package com.behrouz.subplayer.dict

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Online sentence translation (used only for phrases, only when connected).
 * Tries Google Translate's public endpoint first, then MyMemory as a fallback.
 */
object Translator {

    data class Result(val text: String, val service: String)

    suspend fun translate(text: String, from: String, to: String): Result = withContext(Dispatchers.IO) {
        val errors = ArrayList<String>()
        try {
            return@withContext google(text, from, to)
        } catch (e: Exception) {
            errors.add("Google: ${e.message}")
        }
        try {
            return@withContext myMemory(text, from, to)
        } catch (e: Exception) {
            errors.add("MyMemory: ${e.message}")
        }
        throw IOException("No connection to a translation service (${errors.joinToString("; ")})")
    }

    private fun google(text: String, from: String, to: String): Result {
        val q = URLEncoder.encode(text, "UTF-8")
        val body = get("https://translate.googleapis.com/translate_a/single?client=gtx&sl=$from&tl=$to&dt=t&q=$q")
        val parts = JSONArray(body).getJSONArray(0)
        val sb = StringBuilder()
        for (i in 0 until parts.length()) {
            val p = parts.optJSONArray(i) ?: continue
            sb.append(p.optString(0))
        }
        val out = sb.toString().trim()
        if (out.isEmpty()) throw IOException("empty answer")
        return Result(out, "Google Translate")
    }

    private fun myMemory(text: String, from: String, to: String): Result {
        val q = URLEncoder.encode(text, "UTF-8")
        val body = get("https://api.mymemory.translated.net/get?q=$q&langpair=$from|$to")
        val out = JSONObject(body).getJSONObject("responseData").optString("translatedText").trim()
        if (out.isEmpty()) throw IOException("empty answer")
        return Result(out, "MyMemory")
    }

    private fun get(url: String): String {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8_000
            readTimeout = 10_000
            setRequestProperty("User-Agent", "Mozilla/5.0 (Android) SubPlayer")
        }
        try {
            if (c.responseCode != 200) throw IOException("HTTP ${c.responseCode}")
            return c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally {
            c.disconnect()
        }
    }
}
