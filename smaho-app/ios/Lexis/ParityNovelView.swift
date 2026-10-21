import SwiftUI
import PhotosUI
import UniformTypeIdentifiers

struct ParityNovelView: View {
    @AppStorage("lexis_model") private var model = ParityDefaults.model
    @State private var title = ""
    @State private var genre = ""
    @State private var characters = ""
    @State private var mood = ""
    @State private var instruction = ""
    @State private var blocks = 3
    @State private var tokens = 2000
    @State private var retryCount = 20
    @State private var blockPrompts = ["", "", ""]
    @State private var result = ""
    @State private var templates: [NovelTemplate] = []
    @State private var novels: [IOSNovel] = []
    @State private var templateName = ""
    @State private var selectedTemplate: UUID?
    @State private var showLibrary = false
    @State private var showSettings = false
    @State private var busy = false
    @State private var progress = ""
    @State private var errorText: String?
    @State private var selectedPhotos: [PhotosPickerItem] = []
    @State private var imageData: [Data] = []
    @State private var generationTask: Task<Void, Never>?

    var body: some View {
        Form {
            Section("小説の設定") {
                TextField("タイトル", text: $title)
                TextField("ジャンル", text: $genre)
                TextField("登場人物", text: $characters, axis: .vertical)
                TextField("雰囲気", text: $mood)
                TextField("小説の指示", text: $instruction, axis: .vertical)
                    .lineLimit(3...8)
                Stepper("生成ブロック数: \(blocks)", value: $blocks, in: 1...30)
                Stepper("最大トークン: \(tokens)", value: $tokens, in: 500...8000, step: 500)
                Stepper("再試行回数: \(retryCount)", value: $retryCount, in: 0...20)
                PhotosPicker(selection: $selectedPhotos, maxSelectionCount: 20, matching: .images) {
                    Label("画像を添付（\(imageData.count)/20）", systemImage: "photo")
                }
                if !imageData.isEmpty {
                    Button("添付画像を削除") { imageData.removeAll(); selectedPhotos.removeAll() }
                }
            }
            Section("ブロックごとの指示") {
                ForEach(blockPrompts.indices, id: \.self) { index in
                    TextField("ブロック\(index + 1)の指示", text: $blockPrompts[index], axis: .vertical)
                }
                HStack {
                    Button("指示を追加") { blockPrompts.append("") }
                    Spacer()
                    Button("最後を削除") {
                        if blockPrompts.count > 1 { blockPrompts.removeLast() }
                    }
                }
            }
            Section("テンプレート") {
                TextField("テンプレート名", text: $templateName)
                Button("現在の設定を保存") { saveTemplate() }
                    .disabled(templateName.trimmingCharacters(in: .whitespaces).isEmpty)
                ForEach(templates) { item in
                    Button("読み込む: \(item.name)") { loadTemplate(item) }
                }
            }
            Section("生成") {
                if busy {
                    ProgressView(progress)
                    Button("生成をキャンセル", role: .destructive) {
                        generationTask?.cancel()
                        busy = false
                        progress = "キャンセルしました"
                    }
                } else {
                    Button("AI小説を生成") { generate(append: false) }
                    Button("続きを生成") { generate(append: true) }
                        .disabled(result.isEmpty)
                }
                if let errorText { Text(errorText).foregroundStyle(.red) }
                TextEditor(text: $result).frame(minHeight: 260)
                Button("端末に保存") { saveNovel() }.disabled(result.isEmpty)
                ShareLink("共有", item: result).disabled(result.isEmpty)
            }
        }
        .navigationTitle("AI小説作成")
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button("小説一覧") { showLibrary = true }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("AI設定") { showSettings = true }
            }
        }
        .navigationDestination(isPresented: $showLibrary) {
            ParityLibraryView(novels: $novels) {
                LocalStore.save(novels, key: ParityDefaults.novelKey)
            }
        }
        .sheet(isPresented: $showSettings) { NavigationStack { AISettingsView() } }
        .onAppear {
            novels = LocalStore.load([IOSNovel].self, key: ParityDefaults.novelKey, fallback: [])
            templates = LocalStore.load([NovelTemplate].self, key: ParityDefaults.templateKey, fallback: [])
        }
        .onChange(of: selectedPhotos) { photos in
            Task {
                var loaded: [Data] = []
                for photo in photos.prefix(20) {
                    if let data = try? await photo.loadTransferable(type: Data.self) {
                        loaded.append(data)
                    }
                }
                imageData = loaded
            }
        }
        .onDisappear { generationTask?.cancel() }
    }

    private func saveNovel() {
        guard !result.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        novels.insert(IOSNovel(title: title.isEmpty ? "無題" : title, body: result), at: 0)
        LocalStore.save(novels, key: ParityDefaults.novelKey)
    }

    private func saveTemplate() {
        let item = NovelTemplate(name: templateName, title: title, genre: genre,
                                 characters: characters, mood: mood, instruction: instruction,
                                 blocks: blocks, tokens: tokens, retryCount: retryCount,
                                 blockPrompts: blockPrompts)
        templates.removeAll { $0.name == item.name }
        templates.insert(item, at: 0)
        LocalStore.save(templates, key: ParityDefaults.templateKey)
    }

    private func loadTemplate(_ item: NovelTemplate) {
        title = item.title
        genre = item.genre
        characters = item.characters
        mood = item.mood
        instruction = item.instruction
        blocks = item.blocks
        tokens = item.tokens
        retryCount = item.retryCount
        blockPrompts = item.blockPrompts.isEmpty ? [""] : item.blockPrompts
    }

    private func generate(append: Bool) {
        let initial = append ? result : ""
        if !append { result = "" }
        busy = true
        errorText = nil
        let plannedBlocks = append ? 1 : blocks
        let prompt = instruction
        let novelTitle = title
        let novelGenre = genre
        let novelCharacters = characters
        let novelMood = mood
        let instructions = blockPrompts
        let images = imageData
        let selectedModel = model
        let retries = retryCount
        generationTask = Task {
            var accumulated = initial
            for index in 0..<plannedBlocks {
                if Task.isCancelled { break }
                progress = "ブロック \(index + 1)/\(plannedBlocks) を生成中"
                var promptText = """
                日本語で小説を執筆してください。既存の本文がある場合は重複させず続きを書いてください。
                タイトル: \(novelTitle)
                ジャンル: \(novelGenre)
                登場人物: \(novelCharacters)
                雰囲気: \(novelMood)
                指示: \(prompt)
                ブロック指示: \(index < instructions.count ? instructions[index] : "")
                既存本文:
                \(accumulated.suffix(16000))
                """
                if accumulated.isEmpty { promptText += "\n冒頭から執筆してください。" }
                var parts: [[String: Any]] = [["type": "text", "text": promptText]]
                if index == 0 {
                    for data in images {
                        parts.append(["type": "image_url", "image_url": [
                            "url": "data:image/jpeg;base64,\(data.base64EncodedString())"
                        ]])
                    }
                }
                var success = false
                for attempt in 0...retries {
                    if Task.isCancelled { break }
                    do {
                        let text = try await OpenRouterService.complete(
                            messages: [["role": "user", "content": parts]],
                            model: selectedModel, key: KeychainStore.load())
                        if Task.isCancelled { break }
                        accumulated += (accumulated.isEmpty ? "" : "\n\n") + text
                        result = accumulated
                        success = true
                        break
                    } catch {
                        if Task.isCancelled { break }
                        let message = error.localizedDescription
                        if message.contains("HTTP 403") || message.contains("PROHIBITED_CONTENT") {
                            errorText = "ブロック\(index + 1)は拒否されたためスキップしました"
                            break
                        }
                        if attempt == retries {
                            errorText = "ブロック\(index + 1): \(message)"
                        } else {
                            try? await Task.sleep(nanoseconds: 1_000_000_000)
                        }
                    }
                }
                if !success && errorText?.contains("スキップ") != true { break }
            }
            if !Task.isCancelled && !accumulated.isEmpty {
                result = accumulated
            }
            busy = false
            progress = ""
        }
    }
}

struct ParityLibraryView: View {
    @Binding var novels: [IOSNovel]
    let persist: () -> Void
    @State private var selected: UUID?

    var body: some View {
        List {
            ForEach($novels) { $novel in
                HStack {
                    Button { novel.bookmarked.toggle(); persist() } label: {
                        Image(systemName: novel.bookmarked ? "star.fill" : "star")
                    }
                    .buttonStyle(.borderless)
                    NavigationLink {
                        ParityNovelDetailView(novel: $novel, persist: persist)
                    } label: {
                        VStack(alignment: .leading) {
                            Text(novel.title).foregroundStyle(.primary)
                            Text(novel.createdAt, style: .date).font(.caption)
                        }
                    }
                }
            }
            .onDelete { offsets in
                novels.remove(atOffsets: offsets)
                persist()
            }
        }
        .navigationTitle("小説一覧")
    }
}

struct ParityNovelDetailView: View {
    @Binding var novel: IOSNovel
    let persist: () -> Void

    var body: some View {
        Form {
            TextField("タイトル", text: $novel.title)
            TextEditor(text: $novel.body).frame(minHeight: 350)
            Toggle("ブックマーク", isOn: $novel.bookmarked)
            Button("変更を保存") { persist() }
            ShareLink("共有", item: novel.body)
        }
        .navigationTitle("小説詳細")
        .onDisappear { persist() }
    }
}
