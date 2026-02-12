# iPhone App (SwiftUI)

## 1. 目的
`WKWebView` で小説投稿サイトを表示する iPhone アプリです。

## 2. 起動方法
1. `brew install xcodegen`（未導入の場合）
2. `cd smaho-app/iphone`
3. `xcodegen generate`
4. 生成された `NovelSiteMobile.xcodeproj` を Xcode で開いて実行

## 3. URL 変更
表示先は `Sources/App/ContentView.swift` の `siteURL` を変更してください。
