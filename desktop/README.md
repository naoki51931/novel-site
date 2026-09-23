# Lexis Novel Desktop (Windows)

既存の novel-site の小説生成入力に合わせた Windows デスクトップ版です。

- Electron 製
- 生成時だけ OpenRouter API に接続
- APIキーは Electron safeStorage で暗号化保存
- R18モード
- TXT / Markdown 保存
- Web版のログイン、DB、課金処理には非依存

OpenRouterを使うため、完全オフライン生成ではなく、生成時にはインターネット接続が必要です。

## 起動

Windows PowerShell:

    cd desktop
    npm install
    npm start

## Windowsインストーラー作成

    cd desktop
    npm install
    npm run dist

desktop/dist/ 以下にNSISインストーラーが生成されます。

## R18モード

既存Web版の AINovelRequest.r18 と同じ考え方で成人向けプロンプトへ切り替えます。
デスクトップ版では登場人物を18歳以上の成人かつ合意のある関係として明示します。
モデル提供者ごとの利用規約・コンテンツポリシーは別途適用されます。
