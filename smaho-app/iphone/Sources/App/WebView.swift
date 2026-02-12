import SwiftUI
import UIKit
import WebKit

struct WebView: UIViewRepresentable {
    @ObservedObject var state: WebViewState

    func makeUIView(context: Context) -> WKWebView {
        state.webView.navigationDelegate = context.coordinator
        return state.webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(state: state)
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        private let state: WebViewState

        init(state: WebViewState) {
            self.state = state
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            state.currentURL = webView.url
            state.syncTabWithCurrentURL()
            state.focusSearchIfNeeded()
        }

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard
                let url = navigationAction.request.url,
                let scheme = url.scheme?.lowercased()
            else {
                decisionHandler(.allow)
                return
            }

            if scheme == "http" || scheme == "https" {
                let host = url.host?.lowercased() ?? ""
                if WebViewState.internalHosts.contains(host) {
                    decisionHandler(.allow)
                } else {
                    UIApplication.shared.open(url)
                    decisionHandler(.cancel)
                }
                return
            }

            if scheme == "mailto" || scheme == "tel" {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }

            decisionHandler(.allow)
        }
    }
}

enum AppTab: Hashable {
    case home
    case search
    case aiChat
    case latest
    case notifications
    case mypage

    var title: String {
        switch self {
        case .home: return "ホーム"
        case .search: return "検索"
        case .aiChat: return "AIチャット"
        case .latest: return "新着"
        case .notifications: return "通知"
        case .mypage: return "マイページ"
        }
    }

    var systemImage: String {
        switch self {
        case .home: return "house"
        case .search: return "magnifyingglass"
        case .aiChat: return "message"
        case .latest: return "clock"
        case .notifications: return "bell"
        case .mypage: return "person"
        }
    }

    var path: String {
        switch self {
        case .home: return "/"
        case .search: return "/?mobile_search=1"
        case .aiChat: return "/ai_chat"
        case .latest: return "/?feed=new"
        case .notifications: return "/notifications"
        case .mypage: return "/mypage"
        }
    }
}

final class WebViewState: ObservableObject {
    static let baseURL = URL(string: "https://shosetsu-toukou-site.org")!
    static let internalHosts = Set(["shosetsu-toukou-site.org", "www.shosetsu-toukou-site.org", "localhost"])

    @Published var selectedTab: AppTab = .home
    @Published var currentURL: URL?
    let webView: WKWebView

    init() {
        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.allowsBackForwardNavigationGestures = true
    }

    func initialLoadIfNeeded() {
        guard webView.url == nil else { return }
        load(tab: .home)
    }

    func load(tab: AppTab) {
        selectedTab = tab
        guard let target = URL(string: tab.path, relativeTo: Self.baseURL)?.absoluteURL else { return }
        webView.load(URLRequest(url: target))
    }

    func syncTabWithCurrentURL() {
        guard let url = webView.url, let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return
        }
        let path = components.path
        let queryItems = Dictionary(uniqueKeysWithValues: (components.queryItems ?? []).map { ($0.name, $0.value ?? "") })

        let next: AppTab
        if path.hasPrefix("/ai_chat") {
            next = .aiChat
        } else if path.hasPrefix("/notifications") {
            next = .notifications
        } else if path.hasPrefix("/mypage") {
            next = .mypage
        } else if path == "/" && queryItems["mobile_search"] == "1" {
            next = .search
        } else if path == "/" && queryItems["feed"] == "new" {
            next = .latest
        } else {
            next = .home
        }

        if selectedTab != next {
            selectedTab = next
        }
    }

    func focusSearchIfNeeded() {
        guard
            let url = webView.url,
            let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
            components.path == "/",
            components.queryItems?.contains(where: { $0.name == "mobile_search" && $0.value == "1" }) == true
        else {
            return
        }

        let js = """
        (function () {
          var candidates = Array.from(document.querySelectorAll('input[type="search"], input[type="text"]'));
          if (!candidates.length) return;
          var target = candidates.find(function (el) {
            var p = (el.placeholder || "").toLowerCase();
            return p.includes("検索") || p.includes("search");
          }) || candidates[0];
          try { target.focus(); } catch (e) {}
        })();
        """
        webView.evaluateJavaScript(js, completionHandler: nil)
    }
}
