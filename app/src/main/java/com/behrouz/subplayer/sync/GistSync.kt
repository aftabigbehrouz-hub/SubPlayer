package com.behrouz.subplayer.sync

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** Keeps the sync document in a private (secret) GitHub gist. Needs a token with the "gist" permission. */
class GistSync(private val token: String) {
    companion object {
        const val FILE = "subplayer-sync.json"
        const val DESCRIPTION = "SubPlayer sync (private)"
        const val TOKEN_PAGE = "https://github.com/settings/tokens/new?scopes=gist&description=SubPlayer%20sync"
    }

    private fun call(method: String, url: String, body: String? = null): String {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 20_000; readTimeout = 60_000
            setRequestProperty("Authorization", "Bearer ${token.trim()}")
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
            setRequestProperty("User-Agent", "SubPlayer")
            if (body != null) { doOutput = true; setRequestProperty("Content-Type", "application/json") }
        }
        try {
            if (body != null) c.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            val code = c.responseCode
            val text = (if (code in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) throw IOException(when (code) {
                401 -> "GitHub token not accepted"
                403, 404 -> "GitHub refused (does the token have the “gist” permission?)"
                else -> "GitHub answered HTTP $code"
            })
            return text
        } finally { c.disconnect() }
    }

    /** Finds the existing SubPlayer gist (or null). */
    fun find(): String? {
        for (page in 1..5) {
            val arr = org.json.JSONArray(call("GET", "https://api.github.com/gists?per_page=100&page=$page"))
            if (arr.length() == 0) return null
            for (i in 0 until arr.length()) {
                val g = arr.getJSONObject(i)
                if (g.optJSONObject("files")?.has(FILE) == true) return g.getString("id")
            }
        }
        return null
    }

    fun create(content: String): String {
        val body = JSONObject().put("description", DESCRIPTION).put("public", false)
            .put("files", JSONObject().put(FILE, JSONObject().put("content", content)))
        return JSONObject(call("POST", "https://api.github.com/gists", body.toString())).getString("id")
    }

    fun read(id: String): String {
        val f = JSONObject(call("GET", "https://api.github.com/gists/$id")).getJSONObject("files").optJSONObject(FILE) ?: return ""
        return if (f.optBoolean("truncated")) call("GET", f.getString("raw_url")) else f.optString("content")
    }

    fun write(id: String, content: String) {
        val body = JSONObject().put("files", JSONObject().put(FILE, JSONObject().put("content", content)))
        call("PATCH", "https://api.github.com/gists/$id", body.toString())
    }
}
