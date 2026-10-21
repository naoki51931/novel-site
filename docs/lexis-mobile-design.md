# Lexis モバイルアプリ設計書（Android現行版 / iOS初期実装）

更新日: 2026-10-21

## 1. 目的と対象

Lexis（https://shosetsu-toukou-site.org）のWebサイトと端末内AI機能を提供するモバイルアプリ。
Android既存実装 `smaho-app/android/` を基準として、iOS初期実装を `smaho-app/ios/` に追加する。
Androidのバージョンは1.0.21で固定。iOSは独立したバージョン0.1.0で開始する。

## 2. Android現行実装の構成

| 機能 | Android実装 | 保存・連携 |
| --- | --- | --- |
| 起動/サイト表示 | `MainActivity`、WebView | 本番Webサイト、ログインCookie |
| 起動時のネイティブ画面 | AI小説作成・AIチャット・AI相談室の96dp縦ボタン | WebViewは裏で初回読込 |
| サイト障害時 | ネイティブ画面を維持、10分間隔の再試行 | アプリが動作している間 |
| AI小説作成 | `NovelGeneratorActivity` | OpenRouter、モデル選択、画像最大20枚、ローカル小説保存 |
| 小説一覧/詳細 | `NovelGeneratorActivity` | 詳細→一覧→生成ページの戻る動線 |
| AIチャット | `AiChatActivity` | 会話履歴、キャラクター設定、モデル、画像最大20枚 |
| AI相談室 | `ConsultationActivity` | スレッド、履歴、モデル、画像最大20枚 |
| 非同期生成 | `NovelGenerationService` | Android foreground service、通知 |
| プッシュ通知 | `NovelFirebaseMessagingService` | Firebase Messaging |
| 認証/投稿 | WebView・OAuthコールバック・端末機能 | Webサイト/ネイティブ連携 |
| APIキー | `EncryptedSharedPreferences` | Android Keystore |
| ダウンロード/共有 | Android DownloadManager等 | 端末ストレージ/共有 |

## 3. iOS初期版アーキテクチャ

- **UI:** SwiftUI、iOS 16以上。端末向け3ボタン、AI小説作成、AIチャット、AI相談室。
- **Web:** WKWebView。初期表示は常にネイティブ3ボタン。メインフレームの正常読込後にWeb表示へ移行。
- **再接続:** 前景動作中に10分ごとに再試行。アプリ復帰時も経過時間を確認。iOSが停止/サスペンド中の正確な10分周期は保証しない。
- **AI:** URLSessionでOpenRouter Chat Completions APIへHTTPS POST。モデルIDを設定可能。
- **秘密情報:** OpenRouter APIキーはKeychainへ保存。コードやUserDefaultsへキーを書かない。
- **端末データ:** 小説一覧・チャット履歴・相談履歴をCodable/JSONでUserDefaultsに保存。Android端末のデータとは自動同期しない。
- **画像:** PhotosPickerで最大20枚選択し、OpenRouterのマルチモーダルメッセージに添付。利用可能なモデルのみ画像入力を処理できる。
- **ナビゲーション:** 小説生成→小説一覧→詳細。iOSの標準戻る操作で詳細→一覧→生成へ戻る。
- **プロジェクト生成:** `project.yml` を XcodeGen で `Lexis.xcodeproj` に変換。Xcodeで署名/実機ビルド。

## 4. 起動・サイト接続状態遷移

```text
アプリ起動
  ↓
[ネイティブ縦3ボタン] ──（ボタン押下）──→ 各ネイティブAI画面
  │
  └── WKWebViewが非表示のままサイト読込
         ├─ 成功（許可ホスト、メインフレーム読込完了）→ [Webサイト表示]
         └─ 失敗/HTTP 5xx → [ネイティブ縦3ボタン]
                                      └─ 10分後に再試行（前景動作中）
```

サイト読込中もボタン操作を阻害しない。通信失敗時は「接続できません」や再接続ボタンを表示しない。

## 5. API通信

- Endpoint: `POST https://openrouter.ai/api/v1/chat/completions`
- Authorization: `Bearer <ユーザーが入力したAPIキー>`
- Body: `model`、`messages`。画像添付は `content` の配列に `image_url` data URL。
- 通信エラー/HTTPエラーはUIに表示。キャンセルはSwift ConcurrencyのTaskキャンセル。
- モデルによっては画像入力不可、レスポンス形式差異あり。必要に応じて対応モデルの制限を追加する。

## 6. iOS初期実装とAndroidとの差分（未実装）

iOSは**実装開始版**でありAndroid完全互換ではない。次は今後の実装対象。

1. Androidの詳細な小説ブロック生成、テンプレート、ブックマーク、投稿/ログイン連携、生成継続・エラー時スキップ処理。
2. AIチャットのキャラクター/性格/作品設定、テンプレート、複数スレッド、会話スタイル等の詳細オプション。
3. AI相談室の複数スレッドや細かな設定。
4. Android foreground serviceに相当する長時間生成の継続。iOSではOS制約に沿う設計が必要。
5. Firebase/APNsプッシュ通知、WebViewのファイルアップロード/ダウンロード細部、OAuthカスタムURLスキーム、共有拡張。
6. iCloud同期、Androidデータ移行、画像添付のサイズ制限・最適化。
7. 実機でのアクセシビリティ/回線切替/大量画像/通信失敗テスト。

## 7. セキュリティと運用

- APIキーはKeychainで保護し、Gitにコミットしない。
- WebサイトはHTTPSでのみ利用する。WebViewのCookieはWebKit管理。
- OpenRouterへの画像送信前にユーザーが画像を選択する。添付画像は選択後にメモリ上で扱う。
- App Store公開にはApple Developer Program、署名、プライバシー表示、利用規約/審査対応が別途必要。

## 8. 受け入れ条件とテスト

- 起動直後は大きな3ボタンが縦表示される。
- Web読込成功後だけWeb画面へ切り替わる。
- 接続不可時は3ボタンのまま、10分後に再試行する（アプリ前景時）。
- 3つのネイティブ機能が開き、閉じられる。
- APIキー保存/モデル変更、生成・送信、エラー表示、キャンセルが動作する。
- 小説を保存し、一覧→詳細→一覧→生成に戻れる。
- チャット/相談履歴がアプリ再起動後も保持される。
- Xcodeのビルドと実機動作は未検証。マージ/公開前にmacOS + Xcodeで検証する。
