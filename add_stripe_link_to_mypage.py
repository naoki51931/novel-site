from pathlib import Path
import re

path = Path("frontend/src/pages/Mypage.jsx")
src = path.read_text(encoding="utf-8")

# すでに追加済みなら何もしない
if "startStripeCheckout" in src:
    print("startStripeCheckout は既に定義されています。スキップします。")
else:
    handler = r'''
async function startStripeCheckout() {
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      alert("ログインが必要です。");
      return;
    }

    const res = await fetch("/api/stripe/create-checkout-session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
      },
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(
        data.detail ||
          `決済セッションの作成に失敗しました (${res.status})`
      );
    }

    if (data.url) {
      window.location.href = data.url;
    } else {
      throw new Error("決済URLが取得できませんでした。");
    }
  } catch (err) {
    console.error(err);
    alert(err.message || "決済の開始に失敗しました。");
  }
}
'''

    # export default function Mypage の前にハンドラを挿入
    if "export default function Mypage" in src:
        src = src.replace(
            "export default function Mypage",
            handler + "\nexport default function Mypage",
            1,
        )
    else:
        print("export default function Mypage が見つかりませんでした。")
        exit(1)

# JSX 内に「プレミアム会員」セクションを差し込む
pattern = r'(return\s*\(\s*\n\s*<div[^>]*>\s*\n)'
insert_block = r"""\1      <section style={{ marginBottom: 24 }}>
        <h2>プレミアム会員</h2>
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

new_src, n = re.subn(pattern, insert_block, src, count=1, flags=re.MULTILINE)

if n == 0:
    print("return (<div...) のパターンが見つからず、セクションを挿入できませんでした。")
    # それでもハンドラだけは書き戻しておく
    path.write_text(src, encoding="utf-8")
else:
    path.write_text(new_src, encoding="utf-8")
    print("✅ Mypage.jsx に Stripe 課金リンクを追加しました。")
