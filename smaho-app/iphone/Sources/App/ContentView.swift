import SwiftUI

struct ContentView: View {
    @StateObject private var webState = WebViewState()

    var body: some View {
        VStack(spacing: 0) {
            WebView(state: webState)
            Divider()
            HStack(spacing: 0) {
                navButton(.home)
                navButton(.search)
                navButton(.aiChat)
                navButton(.latest)
                navButton(.notifications)
                navButton(.mypage)
            }
            .padding(.vertical, 8)
            .background(Color(.systemBackground))
        }
        .onAppear {
            webState.initialLoadIfNeeded()
        }
        .ignoresSafeArea(edges: .bottom)
    }

    @ViewBuilder
    private func navButton(_ tab: AppTab) -> some View {
        Button {
            webState.load(tab: tab)
        } label: {
            VStack(spacing: 3) {
                Image(systemName: tab.systemImage)
                    .font(.system(size: 18, weight: .semibold))
                Text(tab.title)
                    .font(.system(size: 10))
            }
            .frame(maxWidth: .infinity)
            .foregroundColor(webState.selectedTab == tab ? .blue : .gray)
        }
    }
}
