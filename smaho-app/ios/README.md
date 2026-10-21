# Lexis iOS (SwiftUI)

Android版の設計に基づくiPhone向けネイティブアプリの初期実装です。設計書: [docs/lexis-mobile-design.md](../../docs/lexis-mobile-design.md)。

## ビルド準備

macOS、Xcode 15以降、[XcodeGen](https://github.com/yonaskolb/XcodeGen) が必要です。

```bash
cd smaho-app/ios
xcodegen generate
open Lexis.xcodeproj
```

Xcodeで `Lexis` ターゲットの Team / Bundle Identifier を自分の署名環境に合わせて設定し、iPhoneシミュレータまたは実機でビルドしてください。iOS 16以上に対応する設計です。

## 機能

- 起動直後に大きなAI小説作成・AIチャット・AI相談室の縦3ボタン。
- 非表示のWKWebViewでサイトへ接続し、成功時にサイト画面へ切り替え。失敗時は10分ごとに再試行（前景中）。
- ネイティブAI小説生成・ローカル小説一覧・詳細閲覧・共有。
- AIチャットとAI相談室。OpenRouter API、モデル設定、APIキーのKeychain保存。
- PhotosPickerで最大20枚の画像選択（画像対応モデルが必要）。

**現状:** ソースコードとXcodeGen定義を追加した段階です。iOSビルド、実機テスト、TestFlight/App Store公開は未実施です。Androidの全機能と同等ではありません。差分は設計書を参照してください。

## GitHub Actions でビルド

GitHubの **Actions → Build Lexis iOS → Run workflow** でmacOSランナー上のビルドを開始できます。mainのiOSソース更新時にも自動でビルドします。

成功すると、該当ワークフロー実行の **Artifacts → Lexis-iOS-Simulator-...** にシミュレータ用 `Lexis.app` のZIPが保存されます。

**重要:** これはビルド確認用で、実機iPhoneにはインストールできません。実機向けIPAの生成・インストールにはApple Developerの署名証明書、プロビジョニングプロファイル、配布方式に応じた登録が必要です。現時点ではIPAの署名・TestFlight配信は自動化していません。GitHub Actionsが実際に成功したかは実行履歴で確認してください。
