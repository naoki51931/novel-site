import SwiftUI
import PhotosUI

struct ParityConsultationView: View {
    @AppStorage("lexis_model") private var model = ParityDefaults.model
    @State private var threads: [ConsultationThread] = []
    @State private var selectedID: UUID?
    @State private var input = ""
    @State private var retryCount = 3
    @State private var selectedPhotos: [PhotosPickerItem] = []
    @State private var imageData: [Data] = []
    @State private var sending = false
    @State private var status = ""
    @State private var showSettings = false
    @State private var requestTask: Task<Void, Never>?

    private var activeIndex: Int? { threads.firstIndex { $0.id == selectedID } }

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Picker("相談スレッド", selection: $selectedID) {
                    ForEach(threads) { item in
                        Text(item.title).tag(Optional(item.id))
                    }
                }
                .pickerStyle(.menu)
                Button {
                    let item = ConsultationThread(title: "新しい相談")
                    threads.insert(item, at: 0)
                    selectedID = item.id
                    persist()
                } label: { Image(systemName: "plus.circle.fill") }
            }
            .padding(.horizontal)
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        if let index = activeIndex {
                            ForEach(threads[index].messages) { entry in
                                VStack(alignment: .leading) {
                                    Text(entry.role == "user" ? "あなた" : "AI")
                                        .font(.caption).foregroundStyle(.secondary)
                                    Text(entry.content)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(12)
                                .background(entry.role == "user" ? Color.blue.opacity(0.12) : Color.gray.opacity(0.12))
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                                .id(entry.id)
                            }
                        }
                    }
                    .padding(.horizontal)
                }
                .onChange(of: activeIndex.flatMap { threads[$0].messages.count } ?? 0) { _ in
                    if let index = activeIndex, let id = threads[index].messages.last?.id {
                        proxy.scrollTo(id, anchor: .bottom)
                    }
                }
            }
            if !status.isEmpty { Text(status).font(.caption).foregroundStyle(.secondary) }
            TextField("相談内容", text: $input, axis: .vertical)
                .lineLimit(2...6)
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
                    Button("送信") { send() }
                        .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && imageData.isEmpty)
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 8)
        }
        .navigationTitle("AI相談室")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("設定") { showSettings = true }
            }
        }
        .sheet(isPresented: $showSettings) {
            NavigationStack {
                Form {
                    Section("通信設定") {
                        Stepper("再試行回数: \(retryCount)", value: $retryCount, in: 0...20)
                        NavigationLink("OpenRouter設定") { AISettingsView() }
                    }
                    Section("スレッド") {
                        Button("現在のスレッドを削除", role: .destructive) {
                            threads.removeAll { $0.id == selectedID }
                            if threads.isEmpty { threads = [ConsultationThread(title: "新しい相談")] }
                            selectedID = threads.first?.id
                            persist()
                        }
                    }
                }
                .navigationTitle("相談室設定")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("閉じる") { showSettings = false }
                    }
                }
            }
        }
        .onAppear {
            threads = LocalStore.load([ConsultationThread].self, key: ParityDefaults.consultationKey,
                                      fallback: [ConsultationThread(title: "新しい相談")])
            if threads.isEmpty { threads = [ConsultationThread(title: "新しい相談")] }
            selectedID = threads.first?.id
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

    private func persist() { LocalStore.save(threads, key: ParityDefaults.consultationKey) }

    private func send() {
        guard let index = activeIndex else { return }
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let photos = imageData
        input = ""; imageData.removeAll(); selectedPhotos.removeAll()
        threads[index].messages.append(ChatMessage(role: "user", content: text.isEmpty ? "画像を確認してください" : text))
        if threads[index].title == "新しい相談" {
            threads[index].title = String(text.prefix(30)).isEmpty ? "画像についての相談" : String(text.prefix(30))
        }
        persist()
        let threadID = threads[index].id
        let history = threads[index].messages
        let selectedModel = model
        sending = true
        status = "相談中…"
        requestTask = Task {
            var payload: [[String: Any]] = [[
                "role": "system",
                "content": "あなたは日本語のAI相談員です。相談内容を整理し、共感的かつ具体的に回答してください。医療・法律などの高リスク分野では専門家への相談も案内してください。"
            ]]
            for (offset, entry) in history.enumerated() {
                if offset == history.count - 1 && !photos.isEmpty {
                    var parts: [[String: Any]] = [["type": "text", "text": entry.content]]
                    for data in photos {
                        parts.append(["type": "image_url", "image_url": [
                            "url": "data:image/jpeg;base64,\(data.base64EncodedString())"
                        ]])
                    }
                    payload.append(["role": entry.role, "content": parts])
                } else {
                    payload.append(["role": entry.role, "content": entry.content])
                }
            }
            for attempt in 0...retryCount {
                if Task.isCancelled { break }
                do {
                    let answer = try await OpenRouterService.complete(messages: payload, model: selectedModel, key: KeychainStore.load())
                    if !Task.isCancelled, let current = threads.firstIndex(where: { $0.id == threadID }) {
                        threads[current].messages.append(ChatMessage(role: "assistant", content: answer))
                        persist()
                        status = ""
                    }
                    break
                } catch {
                    if Task.isCancelled { break }
                    if attempt == retryCount {
                        status = error.localizedDescription
                    } else {
                        try? await Task.sleep(nanoseconds: 1_000_000_000)
                    }
                }
            }
            sending = false
        }
    }
}
