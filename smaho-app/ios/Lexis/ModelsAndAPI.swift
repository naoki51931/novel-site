import Foundation
import Security

enum LexisConfig {
    static let site = URL(string: "https://shosetsu-toukou-site.org")!
    static let allowedHosts: Set<String> = ["shosetsu-toukou-site.org", "www.shosetsu-toukou-site.org"]
    static let retryInterval: TimeInterval = 600
}

enum KeychainStore {
    private static let account = "openrouter_api_key"
    static func save(_ value: String) {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: "Lexis",
                                    kSecAttrAccount as String: account]
        SecItemDelete(query as CFDictionary)
        guard !value.isEmpty else { return }
        var data = query
        data[kSecValueData as String] = Data(value.utf8)
        data[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(data as CFDictionary, nil)
    }
    static func load() -> String {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                    kSecAttrService as String: "Lexis",
                                    kSecAttrAccount as String: account,
                                    kSecReturnData as String: true,
                                    kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return "" }
        return String(data: data, encoding: .utf8) ?? ""
    }
}

struct ChatMessage: Codable, Identifiable {
    var id = UUID()
    var role: String
    var content: String
}

struct SavedNovel: Codable, Identifiable {
    var id = UUID()
    var title: String
    var body: String
    var createdAt = Date()
}

enum LocalStore {
    static func load<T: Decodable>(_ type: T.Type, key: String, fallback: T) -> T {
        guard let data = UserDefaults.standard.data(forKey: key),
              let value = try? JSONDecoder().decode(T.self, from: data) else { return fallback }
        return value
    }
    static func save<T: Encodable>(_ value: T, key: String) {
        guard let data = try? JSONEncoder().encode(value) else { return }
        UserDefaults.standard.set(data, forKey: key)
    }
}

struct OpenRouterService {
    struct CompletionResponse: Decodable {
        struct Choice: Decodable {
            struct Message: Decodable { let content: String? }
            let message: Message
        }
        struct APIError: Decodable { let message: String? }
        let choices: [Choice]?
        let error: APIError?
    }

    static func complete(messages: [[String: Any]], model: String, key: String) async throws -> String {
        guard !key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw APIIssue.message("設定からOpenRouter APIキーを登録してください")
        }
        guard !model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw APIIssue.message("モデル名を入力してください")
        }
        var request = URLRequest(url: URL(string: "https://openrouter.ai/api/v1/chat/completions")!)
        request.httpMethod = "POST"
        request.timeoutInterval = 180
        request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("https://shosetsu-toukou-site.org", forHTTPHeaderField: "HTTP-Referer")
        request.setValue("Lexis iOS", forHTTPHeaderField: "X-Title")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "model": model, "messages": messages
        ])
        let (data, response) = try await URLSession.shared.data(for: request)
        let result = try? JSONDecoder().decode(CompletionResponse.self, from: data)
        guard let http = response as? HTTPURLResponse else {
            throw APIIssue.message("通信結果を取得できませんでした")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw APIIssue.message("HTTP \(http.statusCode): \(result?.error?.message ?? "AI APIエラー")")
        }
        guard let answer = result?.choices?.first?.message.content, !answer.isEmpty else {
            throw APIIssue.message("AIから返信がありませんでした")
        }
        return answer
    }
}

enum APIIssue: LocalizedError {
    case message(String)
    var errorDescription: String? {
        if case .message(let value) = self { return value }
        return nil
    }
}
