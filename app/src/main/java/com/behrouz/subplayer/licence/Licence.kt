package com.behrouz.subplayer.licence

import android.annotation.SuppressLint
import android.content.Context
import android.provider.Settings
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.PKCS8EncodedKeySpec
import java.security.spec.X509EncodedKeySpec

/**
 * Per-phone activation.
 *
 *  - Every phone shows a DEVICE CODE (derived from Android's per-app device id).
 *  - The owner turns "device code + buyer name" into an ACTIVATION CODE by signing it with
 *    his private key (ECDSA P-256). Only the matching public key is inside the app, so
 *    nobody else can create codes, and a code only works on the phone it was made for.
 *
 * Activation code = BASE32(payload) "." BASE32(signature), payload = "SP1|<device>|<name>".
 */
object Licence {

    const val PUBLIC_KEY =
        "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE8Y3bSq60qPtp/kJ28JJaSeUcjoAjSGSw1+yIH7Xs55Xb9Xx2YHpWAUSYMBBa0JR45Oo55RV0Tm9M7n53XKRE4g=="

    data class Holder(val name: String, val device: String)

    @SuppressLint("HardwareIds")
    fun deviceCode(ctx: Context): String {
        val id = Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        return codeFor(id)
    }

    /** 10 characters, shown as XXXXX-XXXXX. */
    fun codeFor(androidId: String): String {
        val h = MessageDigest.getInstance("SHA-256").digest("SubPlayer-device:$androidId".toByteArray())
        val b = Base32.encode(h).take(10)
        return b.substring(0, 5) + "-" + b.substring(5)
    }

    fun payload(device: String, name: String) = "SP1|${device.trim().uppercase()}|${name.trim()}"

    /** Owner side: create an activation code. [privateKey] = base64 PKCS#8 (from the private key file). */
    fun create(privateKey: String, device: String, name: String): String {
        val p = payload(device, name).toByteArray(Charsets.UTF_8)
        val sig = Signature.getInstance("SHA256withECDSA").run {
            initSign(KeyFactory.getInstance("EC").generatePrivate(PKCS8EncodedKeySpec(B64.decode(privateKey))))
            update(p)
            sign()
        }
        return Base32.encode(p) + "." + Base32.encode(sig)
    }

    /** Returns who the code belongs to if it is genuine and made for [device]; otherwise null. */
    fun verify(code: String, device: String, publicKey: String = PUBLIC_KEY): Holder? = try {
        val clean = code.filterNot { it.isWhitespace() }.uppercase()
        val parts = clean.split('.')
        if (parts.size != 2) null else {
            val p = Base32.decode(parts[0])
            val sig = Base32.decode(parts[1])
            val ok = Signature.getInstance("SHA256withECDSA").run {
                initVerify(KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(B64.decode(publicKey))))
                update(p)
                verify(sig)
            }
            val f = String(p, Charsets.UTF_8).split('|', limit = 3)
            if (ok && f.size == 3 && f[0] == "SP1" && f[1] == device.trim().uppercase()) Holder(f[2], f[1]) else null
        }
    } catch (_: Exception) {
        null
    }

    /** True if [privateKey] is the owner's real key (it signs something the app's public key accepts). */
    fun isOwnerKey(privateKey: String): Boolean = try {
        verify(create(privateKey.trim(), "TEST0-TEST0", "owner-check"), "TEST0-TEST0") != null
    } catch (_: Exception) {
        false
    }

    // ------------------------------------------------------------------ storage

    private fun prefs(ctx: Context) = ctx.getSharedPreferences("licence", Context.MODE_PRIVATE)

    fun current(ctx: Context): Holder? =
        prefs(ctx).getString("code", null)?.let { verify(it, deviceCode(ctx)) }

    fun activate(ctx: Context, code: String): Holder? {
        val h = verify(code, deviceCode(ctx)) ?: return null
        prefs(ctx).edit().putString("code", code.filterNot { it.isWhitespace() }).apply()
        return h
    }

    fun ownerKey(ctx: Context): String? = prefs(ctx).getString("owner", null)

    /** Owner unlock: stores the private key on this phone only, and activates this phone. */
    fun becomeOwner(ctx: Context, privateKey: String, name: String): Holder? {
        val key = privateKey.filterNot { it.isWhitespace() }
        if (!isOwnerKey(key)) return null
        prefs(ctx).edit().putString("owner", key).apply()
        return activate(ctx, create(key, deviceCode(ctx), name.ifBlank { "Owner" }))
    }

    fun forgetOwnerKey(ctx: Context) = prefs(ctx).edit().remove("owner").apply()

    // ------------------------------------------------------------------ free trial

    const val TRIAL_DAYS = 10
    const val SELLER_TELEGRAM = "Bgilone"
    private const val DAY = 24L * 60 * 60 * 1000

    /**
     * Days left in the free trial (0 = ended). Pure function, unit-tested.
     * If the phone's clock has been turned back more than a day before the last time the app
     * was used, the trial counts as ended (stops "change the date" tricks).
     */
    fun trialDaysLeft(start: Long, now: Long, lastSeen: Long, days: Int = TRIAL_DAYS): Int {
        if (now + DAY < lastSeen) return 0
        val end = start + days * DAY
        if (now >= end) return 0
        return ((end - now + DAY - 1) / DAY).toInt().coerceIn(1, days)
    }

    fun trialEnd(ctx: Context) = trialStart(ctx) + TRIAL_DAYS * DAY

    /** First use of the app (the earlier of first launch and first install). */
    fun trialStart(ctx: Context): Long {
        val p = prefs(ctx)
        val saved = p.getLong("trial_start", 0L)
        if (saved > 0) return saved
        val installed = try {
            ctx.packageManager.getPackageInfo(ctx.packageName, 0).firstInstallTime
        } catch (_: Exception) { System.currentTimeMillis() }
        val start = minOf(installed, System.currentTimeMillis())
        p.edit().putLong("trial_start", start).apply()
        return start
    }

    /** Call on every app start; returns days left and records "last seen". */
    fun checkTrial(ctx: Context): Int {
        val p = prefs(ctx)
        val now = System.currentTimeMillis()
        val last = p.getLong("last_seen", 0L)
        val left = trialDaysLeft(trialStart(ctx), now, last)
        if (now > last) p.edit().putLong("last_seen", now).apply()
        return left
    }
}

/** RFC 4648 Base32 without padding (letters + digits only: survives chat apps and is case-insensitive). */
object Base32 {
    private const val ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

    fun encode(data: ByteArray): String {
        val sb = StringBuilder()
        var buffer = 0
        var bits = 0
        for (b in data) {
            buffer = (buffer shl 8) or (b.toInt() and 0xFF)
            bits += 8
            while (bits >= 5) {
                sb.append(ALPHABET[(buffer shr (bits - 5)) and 31])
                bits -= 5
            }
        }
        if (bits > 0) sb.append(ALPHABET[(buffer shl (5 - bits)) and 31])
        return sb.toString()
    }

    fun decode(text: String): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        var buffer = 0
        var bits = 0
        for (c in text.trimEnd('=')) {
            val v = ALPHABET.indexOf(c.uppercaseChar())
            require(v >= 0) { "bad character" }
            buffer = (buffer shl 5) or v
            bits += 5
            if (bits >= 8) {
                out.write((buffer shr (bits - 8)) and 0xFF)
                bits -= 8
            }
        }
        return out.toByteArray()
    }
}

/** Minimal standard Base64 decoder (java.util.Base64 needs Android 8; this app supports 7). */
object B64 {
    private const val ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

    fun decode(text: String): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        var buffer = 0
        var bits = 0
        for (c in text) {
            if (c == '=' || c.isWhitespace()) continue
            val v = ALPHABET.indexOf(c)
            require(v >= 0) { "bad base64" }
            buffer = (buffer shl 6) or v
            bits += 6
            if (bits >= 8) {
                out.write((buffer shr (bits - 8)) and 0xFF)
                bits -= 8
            }
        }
        return out.toByteArray()
    }
}
