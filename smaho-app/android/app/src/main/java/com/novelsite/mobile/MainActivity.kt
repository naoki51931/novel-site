package com.novelsite.mobile

import android.Manifest
import android.annotation.SuppressLint
import android.app.DownloadManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.JavascriptInterface
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebStorage
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.core.net.toUri
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import org.json.JSONObject
import java.net.URI

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var progressBar: ProgressBar
    private lateinit var bottomNav: LinearLayout
    private lateinit var navHome: TextView
    private lateinit var navSearch: TextView
    private lateinit var navAiChat: TextView
    private lateinit var navNew: TextView
    private lateinit var navNotifications: TextView
    private lateinit var navMypage: TextView
    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null
    private val nativeFormBridge = NativeFormBridge()
    private var nextNotificationId = 1000

    companion object {
        // 本番URLに切り替える場合はここを書き換え
        private const val SITE_URL = "https://shosetsu-toukou-site.org"
        private const val APP_UA_MARKER = "NovelSiteAndroidApp/1.0"
        private val INTERNAL_HOSTS = setOf(
            "shosetsu-toukou-site.org",
            "www.shosetsu-toukou-site.org",
            "10.0.2.2",
            "localhost"
        )
        private const val HOME_PATH = "/"
        private const val SEARCH_PATH = "/?mobile_search=1"
        private const val AI_CHAT_PATH = "/ai_chat"
        private const val NEW_PATH = "/?feed=new"
        private const val NOTIFICATIONS_PATH = "/notifications"
        private const val MYPAGE_PATH = "/mypage"
        private const val AI_NOTIFICATION_CHANNEL_ID = "ai_generation"
        private const val AI_NOTIFICATION_CHANNEL_NAME = "AI Generation"
    }

    private val filePickerLauncher =
        registerForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
            fileChooserCallback?.onReceiveValue(uris.toTypedArray())
            fileChooserCallback = null
        }

    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (!granted) {
                // permission denied: notifications are optional
            }
        }

    private val backPressedCallback = object : OnBackPressedCallback(true) {
        override fun handleOnBackPressed() {
            if (webView.canGoBack()) {
                webView.goBack()
            } else {
                finish()
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        swipeRefresh = findViewById(R.id.swipeRefresh)
        progressBar = findViewById(R.id.progressBar)
        bottomNav = findViewById(R.id.bottomNav)
        navHome = findViewById(R.id.navHome)
        navSearch = findViewById(R.id.navSearch)
        navAiChat = findViewById(R.id.navAiChat)
        navNew = findViewById(R.id.navNew)
        navNotifications = findViewById(R.id.navNotifications)
        navMypage = findViewById(R.id.navMypage)

        onBackPressedDispatcher.addCallback(this, backPressedCallback)
        createNotificationChannel()
        requestNotificationPermissionIfNeeded()
        MobilePushRegistrar.ensureFirebaseApp(this)

        setupWebView()
        clearWebViewCacheForFreshAssets()
        setupDownloadBehavior()
        setupPullToRefresh()
        setupBottomNav()

        if (savedInstanceState == null) {
            webView.loadUrl(resolveIntentUrl(intent) ?: SITE_URL)
        } else {
            webView.restoreState(savedInstanceState)
        }
    }

    private fun setupPullToRefresh() {
        swipeRefresh.setOnRefreshListener { webView.reload() }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            AI_NOTIFICATION_CHANNEL_ID,
            AI_NOTIFICATION_CHANNEL_NAME,
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "AI novel generation completion notifications"
        }
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(channel)
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun showAiGenerationNotification(title: String, body: String, targetUrl: String?) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) return
        }

        val destination = when {
            targetUrl.isNullOrBlank() -> "$SITE_URL/ai-novel"
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

        val notification = NotificationCompat.Builder(this, AI_NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title.ifBlank { "AI小説生成が完了しました" })
            .setContentText(body.ifBlank { "タップして結果を確認" })
            .setStyle(NotificationCompat.BigTextStyle().bigText(body.ifBlank { "タップして結果を確認" }))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pendingIntent)
            .build()

        NotificationManagerCompat.from(this).notify(nextNotificationId++, notification)
    }

    private fun showSiteNotification(title: String, body: String, targetUrl: String?) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) return
        }

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

        val notification = NotificationCompat.Builder(this, AI_NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title.ifBlank { "新しい通知があります" })
            .setContentText(body.ifBlank { "タップして確認" })
            .setStyle(NotificationCompat.BigTextStyle().bigText(body.ifBlank { "タップして確認" }))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pendingIntent)
            .build()

        NotificationManagerCompat.from(this).notify(nextNotificationId++, notification)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadsImagesAutomatically = true
            allowFileAccess = true
            databaseEnabled = true
            mediaPlaybackRequiresUserGesture = false
            setSupportMultipleWindows(true)
            userAgentString = "$userAgentString $APP_UA_MARKER"
            cacheMode = WebSettings.LOAD_NO_CACHE
        }

        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(webView, true)
        webView.addJavascriptInterface(nativeFormBridge, "AndroidFormBridge")

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: android.webkit.WebResourceRequest?
            ): Boolean {
                val uri = request?.url?.toString() ?: return false
                return handleCustomUri(uri)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                swipeRefresh.isRefreshing = false
                syncBottomNavByUrl(url)
                focusSearchIfNeeded(url)
                super.onPageFinished(view, url)
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progressBar.progress = newProgress
                progressBar.visibility = if (newProgress in 1..99) ProgressBar.VISIBLE else ProgressBar.GONE
                super.onProgressChanged(view, newProgress)
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                fileChooserCallback?.onReceiveValue(null)
                fileChooserCallback = filePathCallback
                filePickerLauncher.launch("*/*")
                return true
            }
        }
    }

    private fun clearWebViewCacheForFreshAssets() {
        runCatching {
            webView.clearCache(true)
            webView.clearHistory()
            WebStorage.getInstance().deleteAllData()
        }
    }

    private fun setupBottomNav() {
        navHome.setOnClickListener { webView.loadUrl("$SITE_URL$HOME_PATH") }
        navSearch.setOnClickListener { webView.loadUrl("$SITE_URL$SEARCH_PATH") }
        navAiChat.setOnClickListener { webView.loadUrl("$SITE_URL$AI_CHAT_PATH") }
        navNew.setOnClickListener { webView.loadUrl("$SITE_URL$NEW_PATH") }
        navNotifications.setOnClickListener { webView.loadUrl("$SITE_URL$NOTIFICATIONS_PATH") }
        navMypage.setOnClickListener { webView.loadUrl("$SITE_URL$MYPAGE_PATH") }
        setTabSelected(navHome)
    }

    private fun syncBottomNavByUrl(rawUrl: String?) {
        val uri = rawUrl?.toUri() ?: return
        val path = uri.path ?: "/"
        val target = when {
            path.startsWith("/ai_chat") -> navAiChat
            path.startsWith("/notifications") -> navNotifications
            path.startsWith("/mypage") -> navMypage
            path == "/" && uri.getQueryParameter("mobile_search") == "1" -> navSearch
            path == "/" && uri.getQueryParameter("feed") == "new" -> navNew
            else -> navHome
        }
        setTabSelected(target)
    }

    private fun setTabSelected(selected: TextView) {
        val tabs = listOf(navHome, navSearch, navAiChat, navNew, navNotifications, navMypage)
        tabs.forEach { tab ->
            val isSelected = tab == selected
            tab.setBackgroundColor(if (isSelected) 0x1A1565C0 else 0x00000000)
            tab.setTextColor(if (isSelected) 0xFF1565C0.toInt() else 0xFF424242.toInt())
            tab.isSelected = isSelected
        }
    }

    private fun focusSearchIfNeeded(rawUrl: String?) {
        val uri = rawUrl?.toUri() ?: return
        if (uri.path != "/" || uri.getQueryParameter("mobile_search") != "1") return
        val js = """
            (function () {
              var candidates = Array.from(document.querySelectorAll('input[type="search"], input[type="text"]'));
              if (!candidates.length) return;
              var target = candidates.find(function (el) {
                var p = (el.placeholder || "").toLowerCase();
                return p.includes("検索") || p.includes("search");
              }) || candidates[0];
              try { target.focus(); } catch (e) {}
            })();
        """.trimIndent()
        webView.evaluateJavascript(js, null)
    }

    private inner class NativeFormBridge {
        @JavascriptInterface
        fun registerMobilePush(authToken: String?) {
            val token = authToken?.trim().orEmpty()
            if (token.isBlank()) return
            MobilePushRegistrar.updateAuthToken(this@MainActivity, token)
        }

        @JavascriptInterface
        fun notifyAiGeneration(payload: String?) {
            runOnUiThread {
                runCatching {
                    val obj = if (payload.isNullOrBlank()) JSONObject() else JSONObject(payload)
                    val title = obj.optString("title").ifBlank { "AI小説生成が完了しました" }
                    val body = obj.optString("body").ifBlank { "タップして結果を確認" }
                    val url = obj.optString("url").ifBlank { "/ai-novel" }
                    showAiGenerationNotification(title, body, url)
                }
            }
        }

        @JavascriptInterface
        fun notifySiteNotification(payload: String?) {
            runOnUiThread {
                runCatching {
                    val obj = if (payload.isNullOrBlank()) JSONObject() else JSONObject(payload)
                    val title = obj.optString("title").ifBlank { "新しい通知があります" }
                    val body = obj.optString("body").ifBlank { "タップして確認" }
                    val url = obj.optString("link_url").ifBlank { "/notifications" }
                    showSiteNotification(title, body, url)
                }
            }
        }
    }

    private fun setupDownloadBehavior() {
        webView.setDownloadListener(
            DownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
                val request = DownloadManager.Request(Uri.parse(url))
                val fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)
                request.setMimeType(mimeType)
                request.setNotificationVisibility(
                    DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
                )
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
                request.addRequestHeader("User-Agent", userAgent)
                request.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url) ?: "")

                val manager = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                manager.enqueue(request)
            }
        )
    }

    private fun handleCustomUri(rawUrl: String): Boolean {
        val uri = runCatching { URI(rawUrl) }.getOrNull() ?: return false
        val scheme = uri.scheme?.lowercase() ?: return false

        if (scheme == "http" || scheme == "https") {
            val host = uri.host?.lowercase()
            if (host != null && INTERNAL_HOSTS.contains(host)) {
                return false
            }
            return openExternal(rawUrl)
        }

        if (scheme == "novelsite") {
            val appUri = Uri.parse(rawUrl)
            val hostPart = appUri.host?.takeIf { it.isNotBlank() }?.let { "/$it" } ?: ""
            val pathPart = appUri.encodedPath ?: ""
            val routePath = (hostPart + pathPart).ifBlank { "/" }
            val query = appUri.encodedQuery?.let { "?$it" } ?: ""
            webView.loadUrl("$SITE_URL$routePath$query")
            return true
        }

        if (scheme == "mailto" || scheme == "tel" || scheme == "intent") {
            return openExternal(rawUrl)
        }

        return false
    }

    private fun openExternal(url: String): Boolean {
        return try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            true
        } catch (_: ActivityNotFoundException) {
            false
        }
    }

    private fun resolveIntentUrl(launchIntent: Intent?): String? {
        val data = launchIntent?.data ?: return null
        val scheme = data.scheme?.lowercase() ?: return null

        if (scheme == "http" || scheme == "https") {
            return data.toString()
        }

        if (scheme == "novelsite") {
            val hostPart = data.host?.takeIf { it.isNotBlank() }?.let { "/$it" } ?: ""
            val pathPart = data.encodedPath ?: ""
            val routePath = (hostPart + pathPart).ifBlank { "/" }
            val query = data.encodedQuery?.let { "?$it" } ?: ""
            return "$SITE_URL$routePath$query"
        }

        return null
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        val nextUrl = resolveIntentUrl(intent) ?: return
        webView.loadUrl(nextUrl)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        webView.saveState(outState)
    }

    override fun onDestroy() {
        fileChooserCallback?.onReceiveValue(null)
        fileChooserCallback = null
        super.onDestroy()
    }
}
