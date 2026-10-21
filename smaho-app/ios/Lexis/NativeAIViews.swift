import SwiftUI
import PhotosUI

struct AISettingsView: View {
    @AppStorage("lexis_model") private var model = "openai/gpt-4o-mini"
    @State private var apiKey = ""
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        Form {
            Section("OpenRouter") {
                SecureField("APIキー", text: $apiKey)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                TextField("モデルID", text: $model)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Link("OpenRouterでAPIキーを取得", destination: URL(string: "https://openrouter.ai/settings/keys")!)
            }
            Button("保存") {
                KeychainStore.save(apiKey)
                dismiss()
            }
        }
        .navigationTitle("AI設定")
        .onAppear { apiKey = KeychainStore.load() }
    }
}

enum ConversationMode {
    case chat, consultation
    var title: String { self == .chat ? "AIチャット" : "AI相談室" }
    var storageKey: String { self == .chat ? "ios_chat_history" : "ios_consultation_history" }
    var systemPrompt: String {
        self == .chat ? "あなたは創作やキャラクターの会話を支援する日本語AIです。" :
                        "あなたは日本語のAI相談員です。相談内容を整理し、具体的で丁寧に回答してください。"
    }
}

struct ConversationView: View {
    let mode: ConversationMode
    @AppStorage("lexis_model") private var model = "openai/gpt-4o-mini"
    @State private var messages: [ChatMessage] = []
    @State private var input = ""
    @State private var sending = false
    @State private var errorText: String?
    @State private var showSettings = false
    @State private var selectedPhotos: [PhotosPickerItem] = []
    @State private var imageData: [Data] = []
    @State private var requestTask: Task<Void, Never>?

    var body: some View {
        VStack(spacing: 8) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(messages) { message in
                            VStack(alignment: message.role == "user" ? .trailing : .leading) {
                                Text(message.role == "user" ? "あなた" : "AI")
                                    .font(.caption).foregroundStyle(.secondary)
                                Text(message.content)
                                    .padding(12)
                                    .background(message.role == "user" ? Color.blue.opacity(0.12) : Color.gray.opacity(0.12))
                                    .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                            .frame(maxWidth: .infinity, alignment: message.role == "user" ? .trailing : .leading)
                            .id(message.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) { _ in
                    if let id = messages.last?.id { proxy.scrollTo(id, anchor: .bottom) }
                }
            }
            if let errorText {
                Text(errorText).foregroundStyle(.red).font(.caption).padding(.horizontal)
            }
            TextField("メッセージ", text: $input, axis: .vertical)
                .lineLimit(2...5)
                .textFieldStyle(.roundedBorder)
                .padding(.horizontal)
            HStack {
                PhotosPicker(selection: $selectedPhotos, maxSelectionCount: 20, matching: .images) {
                    Label("画像", systemImage: "photo")
                }
                Text("\(imageData.count)/20").font(.caption)
                if !imageData.isEmpty {
                    Button("画像削除") { imageData.removeAll(); selectedPhotos.removeAll() }
                }
                Spacer()
                if sending {
                    Button("キャンセル") { requestTask?.cancel(); sending = false }
                } else {
                    Button("送信") { send() }
                        .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && imageData.isEmpty)
                }
            }
            .padding()
        }
        .navigationTitle(mode.title)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("履歴消去") { messages.removeAll(); persist() }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("設定") { showSettings = true }
            }
        }
        .sheet(isPresented: $showSettings) { NavigationStack { AISettingsView() } }
        .onAppear { messages = LocalStore.load([ChatMessage].self, key: mode.storageKey, fallback: []) }
        .onChange(of: selectedPhotos) { items in
            Task {
                var loaded: [Data] = []
                for item in items.prefix(20) {
                    if let data = try? await item.loadTransferable(type: Data.self) { loaded.append(data) }
                }
                imageData = loaded
            }
        }
        .onDisappear { requestTask?.cancel() }
    }

    private func persist() { LocalStore.save(messages, key: mode.storageKey) }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let photos = imageData
        input = ""; imageData = []; selectedPhotos = []
        messages.append(ChatMessage(role: "user", content: text.isEmpty ? "画像を送信" : text))
        persist()
        errorText = nil
        sending = true
        let history = messages
        requestTask = Task {
            do {
                var payload: [[String: Any]] = [["role": "system", "content": mode.systemPrompt]]
                for (index, message) in history.enumerated() {
                    if index == history.count - 1 && !photos.isEmpty {
                        var parts: [[String: Any]] = [["type": "text", "text": text.isEmpty ? "画像を確認してください" : text]]
                        for data in photos {
                            parts.append(["type": "image_url", "image_url": [
                                "url": "data:image/jpeg;base64,\(data.base64EncodedString())"
                            ]])
                        }
                        payload.append(["role": "user", "content": parts])
                    } else {
                        payload.append(["role": message.role, "content": message.content])
                    }
                }
                let answer = try await OpenRouterService.complete(messages: payload, model: model, key: KeychainStore.load())
                guard !Task.isCancelled else { return }
                messages.append(ChatMessage(role: "assistant", content: answer))
                persist()
            } catch {
                if !Task.isCancelled { errorText = error.localizedDescription }
            }
            sending = false
        }
    }
}

struct NovelGeneratorView: View {
    @AppStorage("lexis_model") private var model = "openai/gpt-4o-mini"
    @State private var title = ""
    @State private var instruction = ""
    @State private var generatedText = ""
    @State private var novels: [SavedNovel] = []
    @State private var showLibrary = false
    @State private var showSettings = false
    @State private var generating = false
    @State private var errorText: String?
    @State private var selectedPhotos: [PhotosPickerItem] = []
    @State private var imageData: [Data] = []
    @State private var requestTask: Task<Void, Never>?

    var body: some View {
        Form {
            Section("小説の設定") {
                TextField("タイトル", text: $title)
                TextField("あらすじ・指示", text: $instruction, axis: .vertical)
                    .lineLimit(4...10)
                PhotosPicker(selection: $selectedPhotos, maxSelectionCount: 20, matching: .images) {
                    Label("画像を添付（\(imageData.count)/20）", systemImage: "photo")
                }
                if !imageData.isEmpty {
                    Button("添付画像を削除") { imageData = []; selectedPhotos = [] }
                }
            }
            Section("生成") {
                if generating {
                    ProgressView("生成中")
                    Button("キャンセル", role: .destructive) { requestTask?.cancel(); generating = false }
                } else {
                    Button("AI小説を生成") { generate() }
                        .disabled(instruction.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                if let errorText { Text(errorText).foregroundStyle(.red) }
                TextEditor(text: $generatedText).frame(minHeight: 220)
                Button("端末に保存") {
                    guard !generatedText.isEmpty else { return }
                    novels.insert(SavedNovel(title: title.isEmpty ? "無題" : title, body: generatedText), at: 0)
                    persist()
                }
                .disabled(generatedText.isEmpty)
                ShareLink("共有", item: generatedText)
                    .disabled(generatedText.isEmpty)
            }
        }
        .navigationTitle("AI小説作成")
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("小説一覧") { showLibrary = true }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("設定") { showSettings = true }
            }
        }
        .sheet(isPresented: $showSettings) { NavigationStack { AISettingsView() } }
        .navigationDestination(isPresented: $showLibrary) {
            NovelLibraryView(novels: $novels, persist: persist)
        }
        .onAppear { novels = LocalStore.load([SavedNovel].self, key: "ios_novel_library", fallback: []) }
        .onChange(of: selectedPhotos) { items in
            Task {
                var loaded: [Data] = []
                for item in items.prefix(20) {
                    if let data = try? await item.loadTransferable(type: Data.self) { loaded.append(data) }
                }
                imageData = loaded
            }
        }
        .onDisappear { requestTask?.cancel() }
    }

    private func persist() { LocalStore.save(novels, key: "ios_novel_library") }

    private func generate() {
        generating = true
        errorText = nil
        let prompt = instruction
        let photos = imageData
        requestTask = Task {
            do {
                var parts: [[String: Any]] = [["type": "text", "text": "次の指示に従って日本語の小説を書いてください。タイトル: \(title)\n\(prompt)"]]
                for data in photos {
                    parts.append(["type": "image_url", "image_url": [
                        "url": "data:image/jpeg;base64,\(data.base64EncodedString())"
                    ]])
                }
                let answer = try await OpenRouterService.complete(messages: [
                    ["role": "user", "content": parts]
                ], model: model, key: KeychainStore.load())
                if !Task.isCancelled { generatedText = answer }
            } catch {
                if !Task.isCancelled { errorText = error.localizedDescription }
            }
            generating = false
        }
    }
}

struct NovelLibraryView: View {
    @Binding var novels: [SavedNovel]
    let persist: () -> Void

    var body: some View {
        List {
            ForEach(novels) { novel in
                NavigationLink(novel.title) {
                    ScrollView {
                        Text(novel.body)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                    }
                    .navigationTitle(novel.title)
                }
            }
            .onDelete { offsets in novels.remove(atOffsets: offsets); persist() }
        }
        .navigationTitle("小説一覧")
    }
}
