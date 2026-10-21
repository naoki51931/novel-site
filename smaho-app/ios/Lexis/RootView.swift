import SwiftUI
import WebKit

@MainActor
final class WebsiteState: ObservableObject {
    @Published var connected = false
    let webView: WKWebView
    private var loadingFailed = false

    init() {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.allowsBackForwardNavigationGestures = true
    }

    func begin() {
        loadingFailed = false
        webView.load(URLRequest(url: LexisConfig.site, cachePolicy: .reloadIgnoringLocalCacheData))
    }

    func didStart() { loadingFailed = false }
    func didFail() { loadingFailed = true; connected = false }
    func didFinish(_ url: URL?) {
        guard !loadingFailed, let host = url?.host?.lowercased(),
              LexisConfig.allowedHosts.contains(host) else { return }
        connected = true
    }
}

struct SiteWebView: UIViewRepresentable {
    @ObservedObject var state: WebsiteState

    func makeCoordinator() -> Coordinator { Coordinator(state: state) }
    func makeUIView(context: Context) -> WKWebView {
        state.webView.navigationDelegate = context.coordinator
        return state.webView
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        let state: WebsiteState
        init(state: WebsiteState) { self.state = state }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            Task { @MainActor in state.didStart() }
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            Task { @MainActor in state.didFail() }
        }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            Task { @MainActor in state.didFail() }
        }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            let url = webView.url
            Task { @MainActor in state.didFinish(url) }
        }
        func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                     decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
            if navigationResponse.isForMainFrame,
               let response = navigationResponse.response as? HTTPURLResponse,
               response.statusCode >= 500 {
                Task { @MainActor in state.didFail() }
                decisionHandler(.cancel)
            } else {
                decisionHandler(.allow)
            }
        }
    }
}

enum NativePage: String, Identifiable {
    case novel, chat, consultation
    var id: String { rawValue }
}

struct RootView: View {
    @StateObject private var website = WebsiteState()
    @Environment(\.scenePhase) private var scenePhase
    @State private var page: NativePage?
    @State private var lastCheck = Date.distantPast

    var body: some View {
        ZStack {
            SiteWebView(state: website)
                .opacity(website.connected ? 1 : 0)
                .allowsHitTesting(website.connected)

            if !website.connected {
                VStack(spacing: 24) {
                    launchButton("AI小説作成", page: .novel)
                    launchButton("AIチャット", page: .chat)
                    launchButton("AI相談室", page: .consultation)
                }
                .padding(.horizontal, 24)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(uiColor: .systemGroupedBackground))
            }
        }
        .sheet(item: $page) { selection in
            NavigationStack {
                Group {
                    switch selection {
                    case .novel: ParityNovelView()
                    case .chat: ParityChatView()
                    case .consultation: ParityConsultationView()
                    }
                }
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("閉じる") { page = nil }
                    }
                }
            }
        }
        .onAppear { checkSite(force: true) }
        .onChange(of: scenePhase) { phase in
            if phase == .active { checkSite(force: false) }
        }
        .onReceive(Timer.publish(every: LexisConfig.retryInterval, on: .main, in: .common).autoconnect()) { _ in
            checkSite(force: false)
        }
    }

    private func checkSite(force: Bool) {
        guard !website.connected else { return }
        guard force || Date().timeIntervalSince(lastCheck) >= LexisConfig.retryInterval else { return }
        lastCheck = Date()
        website.begin()
    }

    private func launchButton(_ title: String, page target: NativePage) -> some View {
        Button { page = target } label: {
            Text(title)
                .font(.system(size: 24, weight: .semibold))
                .frame(maxWidth: .infinity)
                .frame(height: 96)
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .accessibilityLabel(title)
    }
}
