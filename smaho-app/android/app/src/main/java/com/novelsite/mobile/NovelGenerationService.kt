package com.novelsite.mobile

import android.app.*
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat

class NovelGenerationService : Service() {
 companion object { const val CHANNEL="lexis_generation"; const val ID=4101 }
 override fun onCreate(){super.onCreate();if(android.os.Build.VERSION.SDK_INT>=26)getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel(CHANNEL,"小説生成",NotificationManager.IMPORTANCE_DEFAULT))}
 override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int{
  val open=PendingIntent.getActivity(this,0,Intent(this,NovelGeneratorActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
  startForeground(ID,NotificationCompat.Builder(this,CHANNEL).setSmallIcon(R.drawable.ic_lexis_with_pen).setContentTitle("Lexis 小説生成中").setContentText("生成中です。タップすると生成画面に戻ります").setContentIntent(open).setOngoing(true).build())
  return START_NOT_STICKY
 }
 override fun onBind(intent:Intent?):IBinder?=null
}