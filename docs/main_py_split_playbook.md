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

2026-05-25 時点:

- `main.py` は `1,957` 行。
- 直前の `5,245` 行から `3,288` 行削減。
- 翻訳運用 helper のうち、`translation complete` 判定、`multilingual_ready` 通知、日次翻訳 bot 本体、翻訳 backfill 用 background helper、`public novel card translation` 解決を `backend/app/translation_helpers.py` へ移した。
- 続けて OAuth の純粋 helper と Stripe / premium / checkout helper を `backend/app/oauth_helpers.py`, `backend/app/stripe_helpers.py` へ移した。
- 続けて `monthly stripe premium sync` の本体と `revalidate_premium_on_login` の実体を `backend/app/stripe_helpers.py` へ移した。
- 続けて `daily translation bot` と `monthly stripe premium sync` の `loop/start` を helper module 側へ移し、`main.py` には startup wiring だけを残した。
- 続けて AI / recommendation 向けの `novel feature docs` と `user/public-chat preference text` helper を `backend/app/ai_source_helpers.py` へ移した。
- 続けて episode publish 後の notification background helper を `backend/app/notification_helpers.py` へ移した。
- 続けて AI job 完了通知 helper を `backend/app/notification_helpers.py` へ移した。
- 続けて AI chat の `engagement learning instruction` helper を `backend/app/ai_chat_scoring_helpers.py` へ移した。
- 続けて AI job runtime / quota / retry / chunked generation helper を `backend/app/ai_job_helpers.py` へ移し、`_run_ai_job` 本体も `main.py` から外した。
- 続けて AI memory routes と public AI chat character detail route を `services/` と `features/` 側へ寄せ、`main.py` から route 本体を削除した。
- 続けて AI job / AI chat の薄い facade を direct alias 化し、`main.py` 上の中継 wrapper 行数を圧縮した。
- 続けて AI guest / quota / usage-log helper 束を `backend/app/ai_access_helpers.py` へ移し、`main.py` 側は互換 export のみへ置き換えた。
- 続けて OAuth の request/redirect/account helper 束を `backend/app/oauth_helpers.py` へ寄せ、`main.py` 側は互換 wrapper へ縮小した。
- 続けて AI chat の同期 facade / utility を direct alias 化し、`main.py` 上の trivial wrapper をまとまって圧縮した。
- 続けて small legacy helper 束を `backend/app/legacy_helpers.py` へ移し、残っていた AI chat async / notification wrapper の一部を `partial` 化して `main.py` の中継行数をさらに圧縮した。
- 続けて文字数集計 / 日次 metric / 言語 / タグ / 押絵メタタグの utility 束を `backend/app/content_helpers.py` へ移し、`main.py` 側は互換 export に縮小した。
- 続けて site 判定 / site-scoped lookup / tag 作成を `backend/app/site_helpers.py` へ、認証 / ユーザーアクセス / premium 判定 helper 束を `backend/app/user_access_helpers.py` へ移し、`main.py` 側は互換 export に縮小した。
- 続けて AI 向け text helper を `backend/app/ai_text_helpers.py` へ、payout / free-reading / episode numbering helper 束を `backend/app/payout_reading_helpers.py` へ移し、`main.py` 側は互換 export に縮小した。
- 続けて AI chat access / gating / editable-character 判定 helper 束を `backend/app/ai_access_helpers.py` へ寄せ、`main.py` 側は互換 export に縮小した。
- 続けて OAuth runtime state helper を `backend/app/oauth_helpers.py` へ寄せ、startup wiring 本体を `backend/app/startup_helpers.py` へ移し、`main.py` 側はイベント登録と互換 export のみへ縮小した。
- 続けて site / OAuth / Stripe の純粋 wrapper を direct alias / `partial` 化し、`normalize_site_key`, `resolve_site_key`, PKCE / OAuth state, OAuth1, Stripe subscription helper などの中継行数をまとめて圧縮した。
- 続けて premium / OAuth / AI chat utility の薄い wrapper を `partial` 化し、`verify_premium_with_stripe`, `revalidate_premium_on_login`, OAuth result helper, AI chat scoring/runtime utility の中継行数をさらに圧縮した。
- 続けて AI novel request helper と AI chat prompt builder 3 本を `partial` 化し、prompt generation 周辺の中継行数をさらに圧縮した。
- 続けて translation runtime の `logger` 依存 wrapper を再整理し、日次翻訳 loop / monthly sync loop / background translation helper の一部を `partial` 化して `main.py` の中継をさらに圧縮した。
- 続けて `generate_episode_assist_candidates` の legacy route を `backend/app/features/ai_episode_assist_routes.py` から service 直呼びへ切り替え、`main.py` から route 本体と不要 import を削除した。
- 続けて daily translation / monthly sync / feed enqueue の runtime state を `translation_helpers.py` / `stripe_helpers.py` 側へ移し、`main.py` から started flag・lock・last-run・cooldown state と一部 wrapper を削除した。
- 続けて未使用になった public feature import を削除し、`main.py` の import 群をさらに整理した。
- 続けて後方参照が理由で残っていた translation / OAuth / monthly sync helper wrapper を runtime `lambda` 経由の `partial` に置き換え、`_is_episode_translation_complete`, `_run_daily_translation_bot_once`, `_run_monthly_stripe_premium_sync_once`, `_background_upsert_*`, `_resolve_public_novel_card_translations`, `_generate_unique_username` の中継行数をさらに圧縮した。
- 続けて helper export / auth helper ブロックの空行を整理し、挙動を変えずに `main.py` を `2,000` 行未満まで圧縮した。

今回までに追加で完了した主な移行:

- `helpers`
  - `_has_recent_multilingual_ready_notification`
  - `_is_novel_translation_complete`
  - `_is_episode_translation_complete`
  - `_notify_multilingual_ready_for_novel`
  - `_notify_multilingual_ready_for_episode`
  - `_run_daily_translation_bot_once`
  - `_background_upsert_episode_translation`
  - `_background_upsert_episode_and_novel_translation`
  - `_background_upsert_novel_translation`
  - `_resolve_public_novel_card_translations`
  - `_translation_author_is_premium`
  - `_can_translate_novel`
  - `_can_translate_episode`
  - `_build_pkce_pair`
  - `_build_oauth_state`
  - `_decode_oauth_state`
  - `_normalize_redirect_path`
  - `_generate_unique_username`
  - `_oauth1_build_auth_header`
  - `_oauth1_base_params`
  - `_stripe_checkout_customer_kwargs`
  - `_create_checkout_session_with_customer_fallback`
  - `_stripe_obj_get`
  - `_stripe_subscription_is_active`
  - `_stripe_subscription_is_monthly`
  - `_find_active_monthly_subscription_by_email`
  - `verify_premium_with_stripe`
  - `cancel_stripe_subscription_for_admin_delete`
  - `_run_monthly_stripe_premium_sync_once`
  - `revalidate_premium_on_login`
  - `_daily_translation_bot_loop`
  - `_start_daily_translation_bot_if_enabled`
  - `_monthly_stripe_premium_sync_loop`
  - `_start_monthly_stripe_premium_sync_if_enabled`
  - `_collect_novel_feature_docs`
  - `_collect_user_preference_text_for_novels`
  - `_collect_public_chat_preference_text`
  - `_background_notify_episode_published`
  - `_notify_ai_job_user`
  - `_build_ai_chat_engagement_learning_instruction`
  - `_serialize_ai_response`
  - `_normalize_chunked_generation_payload`
  - `_build_chunked_novel_prompt`
  - `_build_chunked_job_response`
  - `_count_ai_jobs_today`
  - `_count_ai_usage_today`
  - `_ai_novel_paid_remaining`
  - `_ai_novel_daily_max_for_user`
  - `_ai_novel_remaining_for_user`
  - `_reserve_ai_novel_generation_slot`
  - `_is_ai_job_expired`
  - `_kill_expired_ai_jobs`
  - `_should_retry_ai_error`
  - `_is_empty_ai_response_error`
  - `_call_ai_with_retry`
  - `_call_ai_with_retry_prompt`
  - `_run_ai_job`
- `services`
  - `list_ai_memory_items_service`
  - `deactivate_ai_memory_item_service`
  - `delete_ai_memory_item_service`
  - `backfill_ai_memory_from_logs_service`
- `modules`
  - `backend/app/ai_access_helpers.py`

2026-05-26 時点:

- `main.py` は `1,334` 行。
- translation / monthly sync / background translation の runtime export 束を `backend/app/runtime_export_builders.py` へ寄せ、`main.py` は `globals().update(...)` の再公開だけに縮小した。
- 続けて残っていた設定値の大きな束を `backend/app/runtime_config.py` へ移し、`main.py` は設定名の import のみを持つ形へ整理した。
- 続けて startup を `@app.on_event("startup")` から `FastAPI(..., lifespan=...)` へ移し、lifecycle の本体は `backend/app/startup_helpers.py` に閉じ込めた。
- 今後は `main.py` に残る互換 export と trivial alias を優先して削り、`main.py` を「起動配線と最低限の runtime wiring」へ寄せる。

2026-05-26 完了判定:

- `main.py` は `1,032` 行。
- route 本体・重い業務ロジック・大きな設定束・startup 本体は `main.py` から外れている。
- 現状の `main.py` は「FastAPI の起動配線」と「互換 export / runtime wiring」が主であり、行数目標・責務目標ともに達成済みとみなす。
- 以後は `main.py` の無理な縮小を既定方針にしない。新規作業は「`main.py` を増やさないこと」を優先し、縮小は明確な利益がある場合のみ再開する。
- `features`
  - `ai_chat_public_character_detail_routes.py`

再開地点メモ:

- `main.py` は `1,957` 行。
- `main.py` の残塊は、ほぼ route 本体と一部 async な AI chat facade。
- 次の一手としては、残る async な AI chat facade を helper 側へさらに寄せるか、route 本体を feature / service 側へ切り出すのがよい。

2026-05-24 時点:

- `main.py` は `5,245` 行。
- 直前の `6,798` 行から `1,553` 行削減。
- `Phase 5 helper 整理` を継続し、翻訳 / UI i18n の facade、`novels` の create/list 本体、`public novels` 共通 helper 束、`public novels ranking/recommended` の route 本体、`episode publish/status helper` を `main.py` から外した。

今回までに追加で完了した主な移行:

- `helpers`
  - translation facade (`_call_translation_ai_json`, `upsert_novel_translation`, `upsert_episode_translation`)
  - UI i18n runtime facade (`_translate_ui_texts`, job watchdog / recovery, job state)
- `modules`
  - `backend/app/i18n_runtime.py` を追加
- `follow-up`
  - `routers/i18n.py` は `I18nTranslateRequest` を新 module 参照へ切替
  - `services/i18n_service.py` は UI i18n の publish timestamp 参照を新 module へ切替
- `novels`
  - `create_novel`
  - `list_novels`
  - `features/novels_routes.py` の legacy wrapper を `services/novels_write_service.py` / `services/novels_read_service.py` へ接続
- `public novels`
  - `_expand_public_search_aliases`
  - `_resolve_public_viewer_age`
  - `_apply_public_novel_age_filter`
  - `_build_public_cover_map`
  - `_build_public_latest_episode_activity_map`
  - `_build_public_comment_count_map`
  - `_build_novel_comment_count_subquery`
  - `_build_episode_comment_count_subquery`
  - `backend/app/public_novel_helpers.py` を追加
  - `list_public_novel_rankings`
  - `list_recommended_public_novels` route wrapper を feature/service 直結に変更
  - `services/public_novels_service.py` に ranking service を追加
- `episode helpers`
  - `normalize_episode_status`
  - `normalize_episode_publish_mode`
  - `normalize_optional_datetime`
  - `resolve_episode_publish_mode`
  - `apply_episode_publish_mode`
  - `publish_scheduled_episodes`
  - `is_episode_draft`
  - `is_novel_draft`
  - `backend/app/episode_publish_helpers.py` を追加

再開地点メモ:

- `main.py` の残りは、通知や dashboard 系の helper、一部 legacy route 補助関数、domain utility が中心。
- 翻訳/UI i18n は runtime module 化したが、`services/admin_i18n_service.py` など一部 service はまだ `legacy.main` 経由参照を残している。必要なら次回は service 側も直接 module 参照へ寄せられる。
- 次の一手は `public novels / novel write` 周辺の helper 束か、`notification / mail / dashboard` の副作用 helper 束を切り出すのが自然。

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
- 無関係なドメインを横断して一気に触らない。
- ただし同一 dependency cluster に属する近接 slice は、同一作業でまとめて移設してよい。

### 3. 変更単位

1 回の PR / 作業では以下のいずれかに限定する。

- 単一ドメインの router/service/repository 化
- 同一 dependency cluster に属する複数の近接 router / schema / helper の同時整理
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

### Phase 0.5: Runtime Wiring 縮小

目的:

- `main.py` に残る「設定束」「startup/lifecycle」「互換 export」「trivial alias」を先に削り、起動配線だけを読める状態へ寄せる。

作業順:

1. 設定値の束を `settings.py` または `runtime_config.py` へ移す。
2. startup / lifecycle を `lifespan` へ移し、`on_event("startup")` を消す。
3. `main.py` の互換 export を builder / helper module 側へさらに寄せる。
4. それでも残る trivial alias を整理する。

ルール:

- `main.py` には設定の評価ロジック本体を残さず、必要な名前だけを import する。
- lifecycle の本体は helper module に置き、`main.py` 側は `FastAPI(..., lifespan=...)` の配線だけにする。
- 既存テストの `monkeypatch(main, "...")` 互換を壊さないため、外へ出した設定値や export 名は `main.py` 上でも公開名を維持する。
- builder 化で import 順依存が増える場合は、即時参照ではなく `lambda` で遅延束縛して元の import 時挙動を守る。

完了条件:

- `main.py` に大きな env/config 束が残っていない。
- `main.py` に `@app.on_event("startup")` が残っていない。
- `main.py` 上の compatibility wiring が純減している。
- `main.py` が約 `1,000` 行前後まで縮み、起動配線ファイルとして読める。

停止条件:

- `main.py` の主な責務が起動配線と runtime wiring のみに収束している。
- 追加の縮小候補が import 集約や alias 圧縮のような低効果なもの中心になっている。
- この状態に達したら、`main.py` 縮小タスクは完了扱いにする。

再開条件:

- 次の 3 点をすべて満たしたときだけ再開してよい。
1. `main.py` に新しい route 本体または業務ロジックが再流入している。
2. `main.py` の行数増加または責務増加が、実際の保守性低下につながっている。
3. 切り出し先が明確で、テスト込みで安全に分離できる塊がある。

再開前の確認ルール:

1. まず `main.py` の現在行数を確認する。
2. 次に `main.py` に残っているのが本当に route 本体や業務ロジックかを確認する。
3. 次に「削ることで可読性が上がるか、逆に builder/import だけ増えて読みにくくならないか」を確認する。
4. この 3 回の確認を通過しない限り、惰性で `main.py` 縮小作業を始めない。

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
- 依存の薄い近接 slice まで含めてよいが、無関係な helper と endpoint を広く同時移設する
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
