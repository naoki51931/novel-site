from pathlib import Path
import re

path = Path("frontend/src/pages/Mypage.jsx")
text = path.read_text(encoding="utf-8")

pattern = re.compile(
    r"""(\s*)<button\s*
\s*type="button"\s*
\s*className="btn btn-border"\s*
\s*onClick={startStripeCheckout}\s*
\s*>\s*
\s*プレミアム会員になる（決済ページへ）\s*
\s*</button>""",
    re.MULTILINE,
)

def repl(m):
    indent = m.group(1) or ""
    return f"""{indent}{{!isPremium && (
{indent}  <button
{indent}    type="button"
{indent}    className="btn btn-border"
{indent}    onClick={startStripeCheckout}
{indent}  >
{indent}    プレミアム会員になる（決済ページへ）
{indent}  </button>
{indent})}}
{indent}{{isPremium && (
{indent}  <p style={{{{ marginTop: 8 }}}}>
{indent}    すでにプレミアム会員中です。ご利用ありがとうございます。
{indent}  </p>
{indent})}}
"""

new_text, n = pattern.subn(repl, text)

if n == 0:
    print("⚠ premium checkout button block not found; no change made")
else:
    path.write_text(new_text, encoding="utf-8")
    print(f"✅ replaced premium checkout button block ({n} occurrence)")
