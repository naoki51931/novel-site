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

2026-05-23 時点:

- `main.py` は `11,058` 行。
- 手順書の開始時 `27,281` 行から `16,223` 行削減。
- 直近の区切りでは、`route 本体の移設` フェーズから `共通 helper 退避` フェーズへ明確に移った。

今回までに追加で完了した主な移行:

- `ai_chat`
  - `access`
  - service 化済み route 群の router 集約
  - `/api/ai/chat`
  - `/api/ai/chat/generate_image`
- `ai_novel`
  - `episode continue`
- `helpers`
  - DB bootstrap 群
  - Redis/cache helper 群
  - rate-limit / abuse helper 群
  - reCAPTCHA / Google CSE helper 群
  - admin auth helper 群
  - sitemap / indexnow / public indexing helper 群

今回追加で作成・更新した主なモジュール:

- `backend/app/schemas_ai_chat.py`
- `backend/app/services/ai_novel_service.py`
- `backend/app/db_bootstrap.py`
- `backend/app/cache_helpers.py`
- `backend/app/rate_limit_helpers.py`
- `backend/app/external_service_helpers.py`
- `backend/app/admin_auth_helpers.py`
- `backend/app/public_indexing_helpers.py`

再開地点メモ:

- `main.py` の大きい route 本体はかなり減り、残りは `Google indexing / Search Console token・publish helper`、`mail / dashboard / notification`、一部の domain helper が中心。
- `public indexing` は helper 化済みだが、`Google indexing` 本体の credential / publish / quota 判定まではまだ `main.py` に残る。
- 次の一手は `Google indexing / Search Console` helper の module 化か、`notification / mail / dashboard` のような副作用 helper 群の退避が自然。
- 現状は `Phase 4` の後半から `Phase 5` の helper 整理フェーズに入っていると見てよい。

2026-05-23 時点:

- `main.py` は `14,880` 行。
- `cleanup` として、`board` の重複 route 本体を `main.py` から削除し、router mount を回帰テストで固定した。
- 次の 1 ドメインとして、service 化済みだった `ai_jobs / ai_novel_drafts` の route 本体を `main.py` から外した。
- 続けて `ai_novel` のうち service 化済みだった `remaining / auto-fill` も `main.py` から外した。
- 続けて `story-agent` も dedicated service/router へ移し、`main.py` から route 本体を外した。
- `.venv` で `test_ai_jobs_service.py`, `test_ai_novel_drafts_service.py`, `test_feed_refactor.py` を通して mount と service 回帰を確認した。

今回までに追加で完了した主な移行:

- `cleanup`
  - `board posts` の重複 route 本体を `main.py` から削除
- `ai_novel`
  - `ai jobs`
  - `ai novel draft / drafts`
  - `remaining`
  - `auto-fill`
  - `story-agent`

再開地点メモ:

- `ai_novel` の `episode continue` はまだ `main.py` に本体が残る。
- `ai_chat/access` には既存 router があるが、他の `ai_chat` route と同居しているため、二重 mount を避けるには切り出し単位を分ける必要がある。
- `ai_chat` は service 呼び出しへ寄っている route もあるが、schema と helper が `main.py` に密集しているため、次回も小さく分けて進める。
- `main.py` には引き続き既存未コミット差分が混在しているため、巻き戻さず差分を足していく。

2026-05-20 時点:

- `main.py` は `17,898` 行。
- 直近の区切りまでで `19,392 -> 17,898`、開始時 `27,281` 行から `9,383` 行削減。
- `Phase 3` 後半から `Phase 4` の入口を継続。`public / search / tags / me / i18n / ai_misc` の薄い route 本体整理が進んだ。

今回までに追加で完了した主な移行:

- `public`
  - `public novels`
- `search`
  - `users`
  - `tags`
- `series`
  - `series novels`
- `me`
  - `tag follows`
  - `scheduled episodes`
- `tags`
  - `list / detail / novels / related`
  - `follow / unfollow / follow-status`
- `i18n`
  - `translate`
  - `dictionary`
- `ai_misc`
  - `tag candidates`
  - `summary candidates`
  - `title candidate`
  - `title candidates`
  - `character terms`
- `cleanup`
  - `dms` は router/service 側に移行済みだった重複 route 本体を `main.py` から削除
  - `novels/{novel_id}` と `novels/{novel_id}/episodes` の孤立 decorator を除去

再開地点メモ:

- `feed` は endpoint 数に対して `_serialize_feed_novels_for_user` などの shared helper 依存がまだ重い。
- `auth` の OAuth は router 側は service 化済みだが、service 本体はまだ `legacy.oauth_*` を呼ぶ薄い wrapper。
- `ai_misc` は `chat / story-agent / continue / jobs / drafts` がまだ重い本体として残っている。
- `main.py` には helper 群と、重い `feed / ai_chat / auth oauth / ai novel` 系がまだ多く残っている。
- 再開時は `feed` のような重い塊に入る前に、`main.py` 側の helper 退避か、service 化済み route の重複除去を優先してよい。

2026-05-20 時点:

- `main.py` は `19,392` 行。
- 直近の区切りまでで `19,938 -> 19,392`、開始時 `27,281` 行から `7,889` 行削減。
- `Phase 3` 後半から `Phase 4` の入口に入っている。

今回までに追加で完了した主な移行:

- `novels` 残り `summary / tag / title candidates`
- `comments`
- `public profile`
- `author dashboard`
- `auth` 本体
  - `register / login / password reset / login start/verify`
  - OAuth helper 本体は `main.py` に残しつつ router は service 経由化
- `payments`
  - `supports checkout`
  - `support plans`
  - `memberships checkout`
  - `ai chat / ai novel addon checkout`
  - `author balance / payout profile`
  - `stripe checkout / webhook`
- `admin payouts`
  - `supports timeline`
  - `payouts timeline / list / preview / generate`
  - `author payout profile`
  - `mark paid / mark failed`
- `admin`
  - `auth`
  - `contact messages`
  - `users`
  - `ai chat token consumers timeline`
  - `ai logs`
  - `email test all users`
  - `user novels`
  - `delete user`
  - `i18n jobs`
  - `i18n retranslate remaining`
  - `board delete`
  - `translations backfill`
  - `indexing urls / submit / carryover`
  - `indexnow submit`
- `public`
  - `contact messages`
- `ai_misc`
  - `ai logs me`
- `other`
  - `series overview`
  - `trending tags`
  - `prerender novels / episodes`
  - `share episode / og-image`
  - `indexnow key file`
  - `sitemap main/static/novels/episodes/authors/tags/index`
  - `robots.txt`

再開地点メモ:

- `payments` は router 上の主要 legacy route 本体を外し終わった。
- `admin` は `payouts` slice まで service 化済み。
- `admin auth / contact / users / ai logs / i18n / board delete / translations backfill / indexing` の route 本体も `main.py` から外し終わった。
- `main.py` には `public novels`, `ai_misc` の候補生成・chat 本体、helper 群がまだ多く残っている。
- この時点でも `main.py` には今回の分割対象とは別の既存未コミット差分が混在しているため、再開時も巻き戻さずに続行する。

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
- `Phase 1`: `novels`, `episodes`, `me`, `other`, `auth`, `payments` は大きく前進。`admin` は `payouts` を除き未着手が多い
- `Phase 2`: 主要対象はほぼ着手済み
- `Phase 3`: `novels`, `episodes`, `comments`, `author dashboard`, `public profile` は主要 endpoint を移行済み
- `Phase 4`: `payments` は主要 endpoint を移行済み。`admin` は着手中

次の優先候補:

1. `public / ai_misc` の legacy wrapper 解消
2. `main.py` helper 群の共通 module 退避

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
