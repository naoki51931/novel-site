# Android App (Kotlin)

## 1. 目的
`WebView` で小説投稿サイトを表示する Android アプリです。

## 2. 起動方法
1. Android Studio で `smaho-app/android` を開く
2. Gradle Sync を実行
3. エミュレータまたは実機で実行

## 3. URL 変更
表示先は `app/src/main/java/com/novelsite/mobile/MainActivity.kt` の `SITE_URL` を変更してください。

## 4. 開発時HTTP
開発中のみ `http://10.0.2.2:5173` を使えるように `network_security_config.xml` を入れています。

## 5. DM Push 通知 (FCM) の必須設定
DM の Android 通知には Firebase 設定が必要です。未設定だとトークン登録されず通知は届きません。

- `FIREBASE_APP_ID`
- `FIREBASE_API_KEY`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_MESSAGING_SENDER_ID`

設定方法はどちらでも可:

1. 環境変数として設定してビルドする
2. `smaho-app/android/gradle.properties` に同名キーで設定する
