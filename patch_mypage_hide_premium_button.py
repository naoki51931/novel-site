from pathlib import Path

path = Path("frontend/src/pages/Mypage.jsx")
text = path.read_text(encoding="utf-8")

old = '''        <button
          type="button"
          className="btn btn-border"
          onClick={startStripeCheckout}
        >
          プレミアム会員になる（決済ページへ）
        </button>
'''

new = '''        {!isPremium && (
          <button
            type="button"
            className="btn btn-border"
            onClick={startStripeCheckout}
          >
            プレミアム会員になる（決済ページへ）
          </button>
        )}
        {isPremium && (
          <p style={{ marginTop: 8 }}>
            すでにプレミアム会員中です。ご利用ありがとうございます。
          </p>
        )}
'''

if old in text:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("✅ replaced premium button with conditional rendering")
else:
    print("⚠ target button block not found; no change made")
