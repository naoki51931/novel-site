# X OAuth ログインが 400 になる主因と対策（codex用）

## 現象

- `/api/auth/oauth/x/callback` が `400 Bad Request`
- X の token エンドポイントで code 交換に失敗

## 主な原因（優先度順）

### 同じ authorization code を 2 回処理している

- X の code は 1 回限り
- callback がリロード / リダイレクト / bot / SPA 再アクセスで二重実行されると `invalid_grant`

対策

- callback で code を一度しか処理しないガードを入れる（短時間メモリ/Redis）
- 2 回目は token 交換せずフロントへリダイレクト

### PKCE の code_verifier 不一致

- state に入れた pkce（code_verifier）と
- token 交換時に送る code_verifier がズレている
- code_challenge を送ってしまっているケースも多い

対策

- token 交換時は必ず code_verifier を送る
- base64url / 生文字列の混同に注意

### redirect_uri mismatch

- authorize と token で redirect_uri が完全一致していない
- http/https、ポート、末尾 `/` の違いで 400

対策

- callback URL を文字列で固定
- nginx 配下でも token 交換時は同一 URL を使用

## 必須ログ（原因確定用）

token 交換レスポンスを必ずログ出力：

```python
logger.error(
  "X TOKEN status=%s body=%s",
  r.status_code,
  r.text
)
```

## 最低限の二重実行ガード（例）

```python
USED_CODES = {}

def mark_code_used(code):
    if code in USED_CODES:
        return False
    USED_CODES[code] = time.time()
    return True
```

callback 冒頭で：

```python
if not mark_code_used(code):
    return RedirectResponse(FRONTEND_ORIGIN + "/login?oauth=retry")
```

## 結論

9 割は「code の二重使用」か「PKCE 不一致」  
token エンドポイントのレスポンス本文を見れば即確定
