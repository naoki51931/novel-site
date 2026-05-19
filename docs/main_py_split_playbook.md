# `backend/app/main.py` 分割手順書

## 目的

- 現在の [`backend/app/main.py`](/home/ubuntu/novel-site/backend/app/main.py) を最終的に `2,000` から `5,000` 行へ圧縮する。
- `main.py` を「FastAPI の起動配線」と「アプリ全体の初期化」中心のファイルにする。
- API 実装本体は `routers/`, `services/`, `repositories/` へ移す。

## 現状

- `main.py` は約 `27,281` 行。
- `backend/app/routers/` はすでに存在するが、一部は `main.py` を呼ぶ legacy wrapper。
- `backend/app/services/` と `backend/app/repositories/` は存在するが、利用はまだ限定的。
- 既存の自動分割レポート:
  - `reports/auto_refactor_main_py/summary.json`
  - 既処理グループ: `ai_misc`, `feed`, `tags`, `public`, `dms`, `board`, `i18n`, `search`, `series`

## 進捗メモ

2026-05-19 時点:

- `main.py` は `24,177` 行。
- 開始時 `27,281` 行から `3,104` 行削減。
- 全体としては `Phase 2` の終盤から `Phase 3` の前半に入っている。

完了済みの主な移行:

- `like / unlike`
- `favorite / unfavorite`
- `follow / unfollow`
- `notifications`
- `me/view-history`
- `profile/me`
- `ai/chat/usage-history`
- `me/favorites`
- `analytics/novels`
- `novels` 読み取り系
- `novels` 更新・削除
- `create_episode`
- `episodes` 基本 CRUD
- `episodes` title candidates
- `episodes` 画像系 `cover-image / illusts`

現在の評価:

- `Phase 0`: 実質完了
- `Phase 1`: `novels`, `episodes`, `me`, `other` は大きく前進。`auth`, `payments`, `admin` は未着手が多い
- `Phase 2`: 主要対象はほぼ着手済み
- `Phase 3`: `novels`, `episodes` は進行中。`comments`, `author dashboard`, `public profile` はまだ残る

次の優先候補:

1. `novels` の残り `summary/tag/title candidates`
2. `comments`
3. `public profile` / `author dashboard`
4. `auth` / `payments`

## 最終形の目安

`main.py` に残してよいもの:

- `FastAPI()` の生成
- middleware / CORS / static mount
- startup / background loop 起動
- router の `include_router`
- 全体共通の依存注入や設定の最低限

`main.py` から出すもの:

- `@app.get/post/...` の各エンドポイント
- 業務ロジック
- DB クエリ
- 外部 API 呼び出し
- ドメインごとの helper 群

## 分割ルール

### 1. レイヤ責務

- `routers/`
  - パス定義
  - request / response の受け渡し
  - `Depends(get_db)` や `Request` の受け取り
  - service 呼び出し
- `services/`
  - 業務ロジック
  - 権限チェック
  - 複数 repository の組み合わせ
  - notification, Stripe, AI, background task の起動
- `repositories/`
  - SQLAlchemy の query / insert / update / delete
  - DB モデルの取得や集計

### 2. 禁止ルール

- `repository` に `Request` や `HTTPException` を持ち込まない。
- `router` に長い分岐や DB クエリを書かない。
- 新規 router から `..main` を直接 import しない。
- 一気に大量移設しない。1 回の作業単位は 1 ドメインまで。

### 3. 変更単位

1 回の PR / 作業では以下のどちらかに限定する。

- 単一ドメインの router/service/repository 化
- 共通 helper 群の退避

### 4. テスト追加ルール

分割と同時に、最低限の回帰テストを追加する。

必須対象:

- 認証
- 課金
- 投稿
- AIチャット

ルール:

1. endpoint を `main.py` から外したら、その slice の回帰テストを同じ作業で足す。
2. service へ移した処理は、まず service 直呼びのテストで固定する。
3. router を増やしたら、mount 漏れを検知するテストも維持する。
4. `Not Found` を出しやすい `me`, `auth`, `novels`, `episodes`, `payments`, `ai_chat` は優先して route 登録確認を入れる。
5. 認証・課金・投稿・AIチャットは、分割完了前に最低 1 本以上の回帰テストがある状態にする。

## 推奨ディレクトリ

追加先の基本形:

- `backend/app/routers/*.py`
- `backend/app/services/*.py`
- `backend/app/repositories/*.py`
- 必要なら `backend/app/core/*.py` または `backend/app/common/*.py`

候補:

- `core/auth.py`
- `core/cache.py`
- `core/rate_limit.py`
- `core/notifications.py`
- `core/startup.py`
- `core/indexing.py`

## 圧縮ロードマップ

### Phase 0: 事前固定

目的:

- `main.py` を直接いじる前に、移設先のルールを固定する。

作業:

1. `routers`, `services`, `repositories` の命名規則を固定する。
2. `main.py` の新規 API 追加を原則停止する。
3. 新規 API は新しい router にだけ追加する。
4. `main.py` の行数を作業ごとに記録する。

完了条件:

- 新規実装が `main.py` に増えない。

想定削減:

- `0` 行

### Phase 1: wrapper router の解消

目的:

- 既存 `routers/*.py` の legacy wrapper を減らす。

優先対象:

- `novels`
- `episodes`
- `auth`
- `payments`
- `admin`
- `me`

作業:

1. `routers/*.py` から `from .. import main as legacy` 呼び出しを洗い出す。
2. 対応する service を作る。
3. router は service を呼ぶだけに変える。
4. 既存の path / payload / response は変えない。

完了条件:

- 対象 router が `main.py` を import しない。

想定削減:

- `2,000` から `4,000` 行

### Phase 2: 軽い CRUD と反応系を先に抜く

目的:

- 依存が比較的軽い API から先に `main.py` を削る。

優先順:

1. `like / unlike`
2. `favorite / unfavorite`
3. `follow / unfollow`
4. `notifications`
5. `view-history`
6. `profile`

作業:

1. 対応 router を切る。
2. service に権限と分岐を移す。
3. repository に DB 更新を移す。
4. `main.py` の該当 endpoint と helper を削除する。

完了条件:

- CRUD 系の小粒 API が `main.py` に残っていない。

想定削減:

- 追加で `3,000` から `5,000` 行

### Phase 3: 中規模ドメインを機能単位で抜く

目的:

- まとまった機能をドメイン単位で外へ出す。

対象:

- `novels`
- `episodes`
- `comments`
- `author dashboard`
- `public profile`

作業:

1. ドメインごとに service を 1 つ作る。
2. DB アクセスを repository へ寄せる。
3. ドメイン内部 helper も service か repository へ移す。
4. 共有 helper は `core/` へ出す。

完了条件:

- 上記ドメインの endpoint 本体が `main.py` にない。

想定削減:

- 追加で `4,000` から `6,000` 行

### Phase 4: 重い認証・決済・通知を抜く

目的:

- 依存が重く、helper が多い機能を分離する。

対象:

- `auth`
- `two_factor`
- `oauth`
- `payments`
- `stripe webhook`
- `email / push / fcm notification`

作業:

1. `auth_service.py`, `payment_service.py`, `notification_service.py` を作る。
2. provider 呼び出しや token 処理を service に寄せる。
3. DB 操作は `user_repository.py`, `payment_repository.py` などに寄せる。
4. 共通 helper は `core/auth.py`, `core/notifications.py` へ出す。

完了条件:

- 認証・決済・通知の業務ロジックが `main.py` から消える。

想定削減:

- 追加で `4,000` から `6,000` 行

### Phase 5: AI / 翻訳 / バッチ系を抜く

目的:

- 長大な helper 群を大きく削る。

対象:

- AI novel
- AI chat 周辺 helper
- translation
- daily / monthly background jobs
- indexing / sitemap の補助処理

作業:

1. 既存 `ai/` と `features/` に寄せられるものを先に移す。
2. バッチ処理は `services/jobs_*.py` または `core/startup.py` に切る。
3. sitemap / indexing は `services/indexing_service.py` へ寄せる。
4. startup では「起動するだけ」にする。

完了条件:

- `main.py` に AI/翻訳系 helper が大量に残っていない。

想定削減:

- 追加で `4,000` から `7,000` 行

### Phase 6: schema 補完・startup 補助を整理

目的:

- 最後まで残りやすい `ensure_*`, flusher, loop 起動をまとめる。

対象:

- `ensure_*_table_columns`
- redis metrics flusher
- translation bot loop
- premium sync loop
- startup hooks

作業:

1. `core/startup.py` を作る。
2. `register_startup_tasks(app)` のような入口を作る。
3. schema 補完は `bootstrap_schema.py` のように分ける。
4. `main.py` の startup は呼び出しだけにする。

完了条件:

- startup ロジックの本体が `main.py` にない。

想定削減:

- 追加で `2,000` から `4,000` 行

## 到達ラインの目安

- Phase 1 完了: `23,000` から `25,000` 行
- Phase 2 完了: `18,000` から `21,000` 行
- Phase 3 完了: `12,000` から `16,000` 行
- Phase 4 完了: `7,000` から `11,000` 行
- Phase 5-6 完了: `2,000` から `5,000` 行

## 実行順のおすすめ

トークン消費と破壊リスクを抑える順番:

1. `like/favorite/follow`
2. `notifications`
3. `profile/me/view-history`
4. `novels`
5. `episodes`
6. `comments`
7. `auth`
8. `payments`
9. `AI / translation`
10. `startup / ensure_*`

## 1 作業ごとのテンプレート

毎回この順で進める。

1. 対象 endpoint を `main.py` から 1 ドメインだけ選ぶ。
2. 対応 router を作るか既存 router を更新する。
3. service に業務ロジックを移す。
4. repository に DB クエリを移す。
5. router から service を呼ぶ形に変える。
6. `main.py` 側の endpoint 本体を削除する。
7. import と未使用 helper を整理する。
8. 該当テストまたは最低限の動作確認を行う。

## 毎回の完了チェック

- path は変わっていない
- response 形式は変わっていない
- `router -> main` の依存が増えていない
- service に SQL が漏れすぎていない
- repository に HTTP 層が漏れていない
- `main.py` の行数が純減している

## やらない方がいい進め方

- `main.py` 全体を一気に自動分割する
- helper と endpoint を同時に大量移設する
- 先に完璧な共通基盤を作ろうとする
- repository を API 単位で細かく切りすぎる
- legacy wrapper を増やして「分割したように見せる」だけで止める

## 目標達成の判断基準

`main.py` が次の状態になっていれば完了扱いでよい。

- `2,000` から `5,000` 行
- endpoint 定義はごく少数かゼロ
- 主要ドメインは `router -> service -> repository` になっている
- startup と app wiring が中心
- 新機能追加時に `main.py` を触る必要がほぼない
