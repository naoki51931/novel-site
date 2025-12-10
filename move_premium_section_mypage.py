from pathlib import Path
import re

path = Path("frontend/src/pages/Mypage.jsx")
text = path.read_text(encoding="utf-8")

# 1. プレミアム会員セクションを既存位置から削除
premium_pattern = re.compile(
    r'\s*<section[^>]*>\s*<h2>プレミアム会員</h2>.*?</section>\s*',
    re.DOTALL
)
new_text, n = premium_pattern.subn("", text)
print(f"remove premium section: {n} sections removed")

text = new_text

# 2. トップに戻るリンクの直後に挿入する HTML
insert_block = """
    <section style={{ marginBottom: 24 }}>
      <h3>プレミアム会員</h3>
      <p style={{ marginBottom: 8, lineHeight: 1.6 }}>
        長文の全文表示などの追加機能を利用するには、プレミアム登録が必要です。
      </p>
      <button
        type="button"
        className="btn btn-border"
        onClick={startStripeCheckout}
      >
        プレミアム会員になる（決済ページへ）
      </button>
    </section>

"""

# 3. 「← トップに戻る」の直後を探す
pattern2 = r'(<div style={{ marginBottom: 12 }}>\s*<Link to="/">← トップに戻る</Link>\s*</div>)'

if re.search(pattern2, text):
    new_text = re.sub(pattern2, r'\1\n' + insert_block, text)
    path.write_text(new_text, encoding="utf-8")
    print("✅ 挿入成功: プレミアム会員リンクをトップに戻るの下へ移動しました")
else:
    print("❌ トップに戻るの位置が見つかりませんでした。ファイル構造を確認してください。")

