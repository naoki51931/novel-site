import SwiftUI
import PhotosUI

struct ParityChatView: View {
    @AppStorage("lexis_model") private var model = ParityDefaults.model
    @AppStorage("ios_character") private var character = ""
    @AppStorage("ios_personality") private var personality = ""
    @AppStorage("ios_subcharacters") private var subcharacters = ""
    @AppStorage("ios_anime_title") private var animeTitle = ""
    @AppStorage("ios_chat_style") private var style = 0
    @AppStorage("ios_chat_length") private var responseLength = 1
    @State private var profiles: [RoleplayProfile] = []
    @State private var entries: [RoleplayEntry] = []
    @State private var input = ""
    @State private var profileName = ""
    @State private var selectedPhotos: [PhotosPickerItem] = []
    @State private var imageData: [Data] = []
    @State private var sending = false
    @State private var status = ""
    @State private var showSettings = false
    @State private var showCharacterSettings = false
    @State private var requestTask: Task<Void, Never>?

    var body: some View {
        VStack(spacing: 8) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(entries) { entry in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(entry.role == "user" ? (entry.mode == "do" ? "行動" : "あなた") : "AI")
                                    .font(.caption).foregroundStyle(.secondary)
                                Text(entry.content).frame(maxWidth: .infinity, alignment: .leading)
                            }
                            .padding(12)
                            .background(entry.role == "user" ? Color.blue.opacity(0.1) : Color.gray.opacity(0.12))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .id(entry.id)
                        }
                    }
                    .padding(.horizontal)
                }
                .onChange(of: entries.count) { _ in
                    if let id = entries.last?.id { proxy.scrollTo(id, anchor: .bottom) }
                }
            }
            if !status.isEmpty { Text(status).font(.caption).foregroundStyle(.secondary) }
            TextField("会話または行動を入力", text: $input, axis: .vertical)
                .lineLimit(2...5)
                .textFieldStyle(.roundedBorder)
                .padding(.horizontal)
            HStack {
                PhotosPicker(selection: $selectedPhotos, maxSelectionCount: 20, matching: .images) {
                    Label("画像 \(imageData.count)", systemImage: "photo")
                }
                if !imageData.isEmpty {
                    Button("削除") { imageData.removeAll(); selectedPhotos.removeAll() }
                }
                Spacer()
                if sending {
                    Button("キャンセル") { requestTask?.cancel(); sending = false }
                } else {
                    Button("発言") { send(mode: "say") }
                    Button("行動") { send(mode: "do") }
                    Button("自動") { send(mode: "auto") }
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 8)
        }
        .navigationTitle("AIチャット")
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("人物設定") { showCharacterSettings = true }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("API設定") { showSettings = true }
            }
        }
        .sheet(isPresented: $showSettings) { NavigationStack { AISettingsView() } }
        .sheet(isPresented: $showCharacterSettings) {
            NavigationStack {
                Form {
                    Section("キャラクター") {
                        TextField("メインキャラクター", text: $character)
                        TextField("性格", text: $personality, axis: .vertical)
                        TextField("サブキャラクター", text: $subcharacters, axis: .vertical)
                        TextField("作品名", text: $animeTitle)
                        Picker("文体", selection: $style) {
                            Text("標準").tag(0)
                            Text("自然な口語").tag(1)
                            Text("くだけた口語").tag(2)
                        }
                        Picker("返答の長さ", selection: $responseLength) {
                            Text("短め").tag(0)
                            Text("標準").tag(1)
                            Text("長め").tag(2)
                        }
                    }
                    Section("人物設定の保存・読込") {
                        TextField("保存名", text: $profileName)
                        Button("人物設定を保存") { saveProfile() }
                        ForEach(profiles) { item in
                            HStack {
                                Button("読込: \(item.name)") { loadProfile(item) }
                                Spacer()
                                Button(role: .destructive) {
                                    profiles.removeAll { $0.id == item.id }
                                    persistProfiles()
                                } label: { Image(systemName: "trash") }
                            }
                        }
                    }
                    Section("会話履歴") {
                        Button("会話履歴を消去", role: .destructive) {
                            entries.removeAll()
                            persistEntries()
                        }
                    }
                }
                .navigationTitle("人物設定")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("閉じる") { showCharacterSettings = false }
                    }
                }
            }
        }
        .onAppear {
            entries = LocalStore.load([RoleplayEntry].self, key: ParityDefaults.chatKey, fallback: [])
            profiles = LocalStore.load([RoleplayProfile].self, key: ParityDefaults.profilesKey, fallback: [])
        }
        .onChange(of: selectedPhotos) { photos in
            Task {
                var data: [Data] = []
                for photo in photos.prefix(20) {
                    if let bytes = try? await photo.loadTransferable(type: Data.self) { data.append(bytes) }
                }
                imageData = data
            }
        }
        .onDisappear { requestTask?.cancel() }
    }

    private func persistEntries() { LocalStore.save(entries, key: ParityDefaults.chatKey) }
    private func persistProfiles() { LocalStore.save(profiles, key: ParityDefaults.profilesKey) }

    private func saveProfile() {
        guard !profileName.isEmpty else { return }
        let item = RoleplayProfile(name: profileName, character: character, personality: personality,
                                   subcharacters: subcharacters, animeTitle: animeTitle)
        profiles.removeAll { $0.name == item.name }
        profiles.insert(item, at: 0)
        persistProfiles()
    }

    private func loadProfile(_ item: RoleplayProfile) {
        character = item.character
        personality = item.personality
        subcharacters = item.subcharacters
        animeTitle = item.animeTitle
    }

    private func systemPrompt() -> String {
        let tone = style == 1 ? "日常的で自然な口語を使う。" : (style == 2 ? "くだけた口語を使う。" : "")
        let length = responseLength == 0 ? "簡潔に返答する。" : (responseLength == 2 ? "詳細に返答する。" : "")
        return """
        登場人物として自然な日本語でロールプレイ会話をしてください。
        メインキャラクター: \(character)
        性格: \(personality)
        サブキャラクター: \(subcharacters)
        作品: \(animeTitle)
        \(tone) \(length)
        """
    }

    private func send(mode: String) {
        let isAuto = mode == "auto"
        let text = isAuto ? "会話の流れに沿って登場キャラクター側から自然に続きを返してください。" :
                            input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty || !imageData.isEmpty else { return }
        let photos = imageData
        input = ""; imageData.removeAll(); selectedPhotos.removeAll()
        if !isAuto {
            entries.append(RoleplayEntry(role: "user", mode: mode, content: text))
            persistEntries()
        }
        sending = true
        status = "生成中…"
        let history = entries
        let system = systemPrompt()
        let chosenModel = model
        requestTask = Task {
            var payload: [[String: Any]] = [["role": "system", "content": system]]
            for (index, entry) in history.enumerated() {
                let value = entry.mode == "do" ? "[行動] \(entry.content)" : entry.content
                if index == history.count - 1 && !photos.isEmpty && !isAuto {
                    var parts: [[String: Any]] = [["type": "text", "text": value.isEmpty ? "画像を確認してください" : value]]
                    for data in photos {
                        parts.append(["type": "image_url", "image_url": [
                            "url": "data:image/jpeg;base64,\(data.base64EncodedString())"
                        ]])
                    }
                    payload.append(["role": entry.role, "content": parts])
                } else {
                    payload.append(["role": entry.role, "content": value])
                }
            }
            if isAuto { payload.append(["role": "user", "content": text]) }
            do {
                let reply = try await OpenRouterService.complete(messages: payload, model: chosenModel, key: KeychainStore.load())
                if !Task.isCancelled {
                    entries.append(RoleplayEntry(role: "assistant", mode: "say", content: reply))
                    persistEntries()
                    status = ""
                }
            } catch {
                if !Task.isCancelled { status = error.localizedDescription }
            }
            sending = false
        }
    }
}
