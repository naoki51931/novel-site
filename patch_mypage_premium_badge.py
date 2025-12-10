from pathlib import Path

path = Path("frontend/src/pages/Mypage.jsx")
text = path.read_text(encoding="utf-8")
orig = text
changed = False

# 1) isPremium state 追加
state_marker = '  const [favorites, setFavorites] = useState([]);\n  const [loading, setLoading] = useState(true);'
if "const [isPremium, setIsPremium]" not in text and state_marker in text:
    replacement = (
        '  const [favorites, setFavorites] = useState([]);\n'
        '  const [isPremium, setIsPremium] = useState(false);\n'
        '  const [loading, setLoading] = useState(true);'
    )
    text = text.replace(state_marker, replacement)
    changed = True
    print("✅ isPremium state を追加しました")

# 2) /api/users/me を叩いて isPremium を更新（favorites 取得 useEffect 内に追加）
favorites_marker = '        const data = await res.json().catch(() => []);\n\n        if (!res.ok) {'
if "setIsPremium" not in text and favorites_marker in text:
    inject = (
        '        const data = await res.json().catch(() => []);\n\n'
        '        if (!res.ok) {\n'
    )
    new_block = (
        '        const data = await res.json().catch(() => []);\n\n'
        '        if (!res.ok) {\n'
        '          console.error("failed to fetch favorites");\n'
        '          return;\n'
        '        }\n\n'
        '        setFavorites(data);\n\n'
        '        // プロフィールを取得してプレミアム会員かどうかを反映\n'
        '        try {\n'
        '          const resProfile = await fetch(`${API_BASE}/api/users/me`, {\n'
        '            headers: {\n'
        '              Authorization: `Bearer ${token}`,\n'
        '            },\n'
        '          });\n'
        '          if (resProfile.ok) {\n'
        '            const profile = await resProfile.json();\n'
        '            setIsPremium(!!profile.is_premium);\n'
        '          }\n'
        '        } catch (e) {\n'
        '          console.error(e);\n'
        '        }\n\n'
        '        return;\n'
    )
    # 既存の setFavorites / console.error ブロックを一旦簡略化して上書きするのではなく、
    # marker の部分を書き換えて、後ろの既存 setFavorites(data); は使わない形にする
    text = text.replace(favorites_marker, new_block)
    changed = True
    print("✅ /api/users/me から isPremium を取得する処理を追加しました")

# 3) 見出しに PREMIUM バッジを追加
heading_old = '<h2 style={{ marginBottom: "1rem" }}>{username} さんのマイページ</h2>'
if 'PREMIUM' not in text and heading_old in text:
    heading_new = (
        '<h2\n'
        '      style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "8px" }}\n'
        '    >\n'
        '      {username} さんのマイページ\n'
        '      {isPremium && (\n'
        '        <span\n'
        '          style={{\n'
        '            display: "inline-block",\n'
        '            padding: "2px 8px",\n'
        '            borderRadius: "999px",\n'
        '            backgroundColor: "#f0b400",\n'
        '            color: "#fff",\n'
        '            fontSize: 12,\n'
        '          }}\n'
        '        >\n'
        '          PREMIUM\n'
        '        </span>\n'
        '      )}\n'
        '    </h2>'
    )
    text = text.replace(heading_old, heading_new)
    changed = True
    print("✅ 見出しに PREMIUM バッジを追加しました")

if changed and text != orig:
    path.write_text(text, encoding="utf-8")
    print("🎉 Mypage.jsx を更新しました")
else:
    print("ℹ 特に変更はありませんでした（既に反映済みの可能性があります）")
