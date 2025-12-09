from pathlib import Path

path = Path("frontend/src/pages/EditNovel.jsx")
src = path.read_text(encoding="utf-8")

changed = False

# 1) state に status を追加
marker_state = (
'  const [ageLimit, setAgeLimit] = useState("all");           // 全年齢 / R15 / R18\n'
'  const [isAIGenerated, setIsAIGenerated] = useState(false); // AI創作フラグ\n'
)
if 'setStatus(' not in src:
    insert_state = marker_state + '  const [status, setStatus] = useState("public"); // 公開ステータス: "public" or "draft"\n'
    if marker_state in src:
        src = src.replace(marker_state, insert_state)
        print("[OK] add status useState")
        changed = True
    else:
        print("[WARN] state marker not found; status useState not inserted")

# 2) fetchNovel で status を反映
marker_fetch = (
'        const data = await res.json();\n'
'        setTitle(data.title || "");\n'
'        setDescription(data.description || "");\n'
'        setAgeLimit(data.age_limit || "all");\n'
'        setIsAIGenerated(!!data.is_ai_generated);\n'
)
if 'setStatus("draft")' not in src:
    insert_fetch = marker_fetch + (
'        // 公開ステータス反映（status がなければ is_public / デフォルト public）\n'
'        if (data.status === "draft" || data.is_public === false) {\n'
'          setStatus("draft");\n'
'        } else {\n'
'          setStatus("public");\n'
'        }\n'
)
    if marker_fetch in src:
        src = src.replace(marker_fetch, insert_fetch)
        print("[OK] fetchNovel: setStatus from API response")
        changed = True
    else:
        print("[WARN] fetch marker not found; status load not inserted")

# 3) ローカルストレージから status を読み込む
marker_load = (
'      if (draft.title) setTitle(draft.title);\n'
'      if (draft.description) setDescription(draft.description);\n'
'      if (draft.ageLimit) setAgeLimit(draft.ageLimit);\n'
'      if (typeof draft.isAIGenerated === "boolean") {\n'
'        setIsAIGenerated(draft.isAIGenerated);\n'
'      }\n'
)
if 'draft.status' not in src:
    insert_load = marker_load + (
'      if (draft.status === "draft" || draft.status === "public") {\n'
'        setStatus(draft.status);\n'
'      }\n'
)
    if marker_load in src:
        src = src.replace(marker_load, insert_load)
        print("[OK] load draft.status from localStorage")
        changed = True
    else:
        print("[WARN] draft load marker not found; status load not inserted")

# 4) 自動保存 payload に status を追加
marker_save = (
'      const payload = {\n'
'        title,\n'
'        description,\n'
'        ageLimit,\n'
'        isAIGenerated,\n'
'        saved_at: new Date().toISOString(),\n'
'      };\n'
)
if 'status,' not in src:
    insert_save = (
'      const payload = {\n'
'        title,\n'
'        description,\n'
'        ageLimit,\n'
'        isAIGenerated,\n'
'        status,\n'
'        saved_at: new Date().toISOString(),\n'
'      };\n'
)
    if marker_save in src:
        src = src.replace(marker_save, insert_save)
        print("[OK] autosave payload: add status")
        changed = True
    else:
        print("[WARN] autosave marker not found; status not added to payload")

# 5) PUT 送信時に is_public / status を送る
marker_body = (
'        body: JSON.stringify({\n'
'          title,\n'
'          description,\n'
'          age_limit: ageLimit,\n'
'          is_ai_generated: isAIGenerated,\n'
'        }),\n'
)
if 'is_public:' not in src:
    insert_body = (
'        body: JSON.stringify({\n'
'          title,\n'
'          description,\n'
'          age_limit: ageLimit,\n'
'          is_ai_generated: isAIGenerated,\n'
'          is_public: status === "public",\n'
'          status,\n'
'        }),\n'
)
    if marker_body in src:
        src = src.replace(marker_body, insert_body)
        print("[OK] update_novel body: add is_public & status")
        changed = True
    else:
        print("[WARN] request body marker not found; is_public/status not added")

# 6) フォームに「公開ステータス」選択 UI を追加
marker_form = (
'        <div style={{ marginBottom: 8 }}>\n'
'          <label>\n'
'            説明（あらすじ）\n'
'            <br />\n'
'            <textarea\n'
'              value={description}\n'
'              onChange={(e) => setDescription(e.target.value)}\n'
'              rows={6}\n'
'              style={{ width: "100%", padding: 4 }}\n'
'            />\n'
'          </label>\n'
'        </div>\n'
'\n'
'        <div style={{ marginBottom: 8 }}>\n'
'          <label>\n'
'            年齢区分\n'
)
if '公開ステータス' not in src:
    insert_form = (
'        <div style={{ marginBottom: 8 }}>\n'
'          <label>\n'
'            説明（あらすじ）\n'
'            <br />\n'
'            <textarea\n'
'              value={description}\n'
'              onChange={(e) => setDescription(e.target.value)}\n'
'              rows={6}\n'
'              style={{ width: "100%", padding: 4 }}\n'
'            />\n'
'          </label>\n'
'        </div>\n'
'\n'
'        <div style={{ marginBottom: 8 }}>\n'
'          <label>\n'
'            公開ステータス\n'
'            <br />\n'
'            <select\n'
'              value={status}\n'
'              onChange={(e) => setStatus(e.target.value)}\n'
'              style={{ width: "100%", padding: 4 }}\n'
'            >\n'
'              <option value="public">公開</option>\n'
'              <option value="draft">下書き</option>\n'
'            </select>\n'
'          </label>\n'
'        </div>\n'
'\n'
'        <div style={{ marginBottom: 8 }}>\n'
'          <label>\n'
'            年齢区分\n'
)
    if marker_form in src:
        src = src.replace(marker_form, insert_form)
        print("[OK] form: add 公開ステータス select")
        changed = True
    else:
        print("[WARN] form marker not found; 公開ステータス UI not inserted")

if changed:
    path.write_text(src, encoding="utf-8")
    print("[DONE] EditNovel.jsx updated")
else:
    print("[INFO] no changes applied (maybe already patched?)")
