package com.novelsite.mobile

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class NovelFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val SITE_URL = "https://shosetsu-toukou-site.org"
        private const val CHANNEL_ID = "ai_generation"
        private const val CHANNEL_NAME = "AI Generation"
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        if (token.isBlank()) return
        MobilePushRegistrar.registerTokenWithStoredAuth(applicationContext, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        createNotificationChannel()

        val data = message.data
        val title = data["title"]
            ?: message.notification?.title
            ?: "新しい通知があります"
        val body = data["body"]
            ?: message.notification?.body
            ?: "タップして確認"
        val url = data["url"] ?: "/notifications"
        showNotification(title, body, url)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "Site and AI notifications"
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager?.createNotificationChannel(channel)
    }

    private fun showNotification(title: String, body: String, targetUrl: String?) {
        val destination = when {
            targetUrl.isNullOrBlank() -> "$SITE_URL/notifications"
            targetUrl.startsWith("http://") || targetUrl.startsWith("https://") -> targetUrl
            else -> "$SITE_URL${if (targetUrl.startsWith("/")) targetUrl else "/$targetUrl"}"
        }
        val intent = Intent(this, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            data = Uri.parse(destination)
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title.ifBlank { "新しい通知があります" })
            .setContentText(body.ifBlank { "タップして確認" })
            .setStyle(NotificationCompat.BigTextStyle().bigText(body.ifBlank { "タップして確認" }))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent)
            .build()
        NotificationManagerCompat.from(this).notify((System.currentTimeMillis() % 100000).toInt(), notification)
    }
}
