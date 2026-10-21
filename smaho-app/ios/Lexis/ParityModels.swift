import Foundation

struct NovelTemplate: Codable, Identifiable {
    var id = UUID()
    var name: String
    var title: String
    var genre: String
    var characters: String
    var mood: String
    var instruction: String
    var blocks: Int
    var tokens: Int
    var retryCount: Int
    var blockPrompts: [String]
}

struct IOSNovel: Codable, Identifiable {
    var id = UUID()
    var title: String
    var body: String
    var bookmarked = false
    var createdAt = Date()
}

struct RoleplayProfile: Codable, Identifiable {
    var id = UUID()
    var name: String
    var character: String
    var personality: String
    var subcharacters: String
    var animeTitle: String
}

struct RoleplayEntry: Codable, Identifiable {
    var id = UUID()
    var role: String
    var mode: String
    var content: String
}

struct ConsultationThread: Codable, Identifiable {
    var id = UUID()
    var title: String
    var messages: [ChatMessage] = []
}

enum ParityDefaults {
    static let model = "openrouter/auto"
    static let novelKey = "ios_parity_novels"
    static let templateKey = "ios_parity_templates"
    static let chatKey = "ios_parity_chat"
    static let profilesKey = "ios_parity_profiles"
    static let consultationKey = "ios_parity_consultations"
}
