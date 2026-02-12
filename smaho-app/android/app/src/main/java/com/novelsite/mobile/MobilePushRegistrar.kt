package com.novelsite.mobile

import android.content.Context
import android.os.Build
import android.provider.Settings
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

object MobilePushRegistrar {
    private const val TAG = "MobilePushRegistrar"
    private const val PREF_NAME = "mobile_push_prefs"
    private const val KEY_AUTH_TOKEN = "auth_token"
    private const val SITE_URL = "https://shosetsu-toukou-site.org"
    private const val REGISTER_URL = "$SITE_URL/api/mobile-push/register"

    fun updateAuthToken(context: Context, authToken: String) {
        val token = authToken.trim()
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_AUTH_TOKEN, token)
            .apply()
        if (token.isNotBlank()) {
            registerCurrentToken(context)
        }
    }

    fun registerCurrentToken(context: Context) {
        val auth = readAuthToken(context)
        if (auth.isNullOrBlank()) return
        if (!ensureFirebaseApp(context)) return
        runCatching {
            FirebaseMessaging.getInstance().token
                .addOnSuccessListener { fcmToken ->
                    if (!fcmToken.isNullOrBlank()) {
                        registerToken(context, auth, fcmToken)
                    }
                }
        }
    }

    fun registerTokenWithStoredAuth(context: Context, fcmToken: String) {
        if (!ensureFirebaseApp(context)) return
        val auth = readAuthToken(context) ?: return
        if (auth.isBlank() || fcmToken.isBlank()) return
        registerToken(context, auth, fcmToken)
    }

    private fun readAuthToken(context: Context): String? {
        return context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
            .getString(KEY_AUTH_TOKEN, null)
            ?.trim()
    }

    private fun registerToken(context: Context, authToken: String, fcmToken: String) {
        val deviceId = runCatching {
            Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        }.getOrNull().orEmpty()
        val appVersion = runCatching {
            val pm = context.packageManager
            val p = pm.getPackageInfo(context.packageName, 0)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                "${p.versionName}(${p.longVersionCode})"
            } else {
                "${p.versionName}(${p.versionCode})"
            }
        }.getOrNull().orEmpty()

        thread(start = true) {
            var conn: HttpURLConnection? = null
            try {
                val payload = JSONObject().apply {
                    put("token", fcmToken)
                    put("platform", "android")
                    put("device_id", deviceId)
                    put("app_version", appVersion)
                }.toString()
                conn = (URL(REGISTER_URL).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 15000
                    readTimeout = 15000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Authorization", "Bearer $authToken")
                }
                OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use {
                    it.write(payload)
                }
                val status = conn.responseCode
                if (status !in 200..299) {
                    Log.w(TAG, "registerToken failed status=$status")
                } else {
                    conn.inputStream?.close()
                }
            } catch (e: Exception) {
                Log.w(TAG, "registerToken exception", e)
            } finally {
                conn?.disconnect()
            }
        }
    }

    fun ensureFirebaseApp(context: Context): Boolean {
        runCatching {
            FirebaseApp.getInstance()
            return true
        }
        val appId = BuildConfig.FIREBASE_APP_ID.trim()
        val apiKey = BuildConfig.FIREBASE_API_KEY.trim()
        val projectId = BuildConfig.FIREBASE_PROJECT_ID.trim()
        val senderId = BuildConfig.FIREBASE_MESSAGING_SENDER_ID.trim()
        if (appId.isBlank() || apiKey.isBlank() || projectId.isBlank() || senderId.isBlank()) {
            Log.w(TAG, "Firebase config missing. BuildConfig values are blank.")
            return false
        }
        return runCatching {
            val options = FirebaseOptions.Builder()
                .setApplicationId(appId)
                .setApiKey(apiKey)
                .setProjectId(projectId)
                .setGcmSenderId(senderId)
                .build()
            FirebaseApp.initializeApp(context, options)
            true
        }.getOrElse { false }
    }
}
