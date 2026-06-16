## main.py 縮小リファクタ手順書

目的: `backend/app/main.py` の責務をアプリ起動・middleware・router登録・lifespan設定へ段階的に縮小する。

現在の対象スライス:
1. 残存する `from app.main import ...` / `main as legacy` 依存を小さな単位で剥がす
2. router は payload 変換と service 呼び出しだけに保つ
3. service に業務処理を集約しつつ、`main.py` の再 export を経由しない
4. service 内の DB 操作は可能な範囲で repository へ寄せる

進め方:
1. `from app.main import ...` / `from .. import main as legacy` を検索して、対象スライスの依存一覧を固定する。
2. 対象 service/router が `main.py` 経由で参照している helper を洗い出し、本来の定義元へ置き換える。
3. 定義元 helper が設定値注入を必要とする場合は、`runtime_config.py` の定数と helper 実装から service 側で局所的に束ねる。
4. router は payload 変換と service 呼び出しだけにする。DB クエリや分岐は置かない。
5. service から SQLAlchemy query を追い出せる箇所を repository へ移す。
6. `main.py` に残る novels 向け互換 export が不要になったことを確認し、次スライスへ進む。

進捗:
1. 完了: `novels`
変更対象:
`routers/novels.py`
`features/novels_routes.py`
`services/novels_read_service.py`
`services/novels_write_service.py`
`repositories/novels_read_repository.py`
`repositories/novels_write_repository.py`
内容:
`main.py` 経由の schema/helper 参照を除去
novels 系 router を薄型化
novels 系 service の query を repository へ移動
検証:
`backend/tests/test_posting_services.py`
`backend/tests`

2. 完了: `episodes`
変更対象:
`services/episodes_write_service.py`
`services/episodes_core_service.py`
`repositories/episodes_write_repository.py`
`repositories/episodes_core_repository.py`
内容:
`main.py` 経由の helper 参照を除去
タグ置換と削除系 DB 操作を repository へ移動
検証:
`backend/tests/test_posting_services.py`
`backend/tests`

3. 完了: `auth`
変更対象:
`routers/auth.py`
`features/auth_routes.py`
`services/auth_service.py`
内容:
`main.py` 経由の schema/helper 参照を除去
auth router を薄型化
補足:
`routers/auth.py` の `create_access_token()` は `two_factor.py` から参照されるため local helper として維持
検証:
`backend/tests/test_auth_service.py`
`backend/tests/test_posting_services.py`
`backend/tests`

4. 完了: `payments`
変更対象:
`routers/payments.py`
`services/payments_service.py`
`repositories/payments_read_repository.py`
`repositories/payments_write_repository.py`
内容:
`main.py` 経由の schema/helper 参照を除去
payment router を薄型化
SupportPlan / Membership / Support / addon purchase 周辺の query を repository へ移動
検証:
`backend/tests/test_posting_services.py`
`backend/tests`

5. 完了: `profile / public_profile / view_history`
変更対象:
`services/profile_service.py`
`services/public_profile_service.py`
`services/view_history_service.py`
内容:
`main.py` 経由の auth/site/cache/schema helper 参照を除去
public profile 系 service を direct import 化
補足:
`public_profile_service.py` にはまだ DB query が多く残っているため、次段で repository 化余地あり
検証:
`backend/tests/test_posting_services.py`
`backend/tests`

次の候補スライス:
1. `board_service`
2. `episode_assets_service`
3. `ai_novel_service`
4. `ai_feature_service`
5. `public_feature_service`
6. `ai_story_agent_service`

確認手順:
1. 対象スライスに対応する focused test を先に回す。
2. 影響範囲の広い既存テストを追加で回す。
3. 最後に `pytest` 全体を回し、失敗があれば今回スライス起因か既存不安定かを切り分ける。

レビュー観点:
- router から `main as legacy` が消えているか
- service が `main.py` 再 export ではなく元モジュールを参照しているか
- repository が query / delete / relation load を引き受けているか
- API 応答 shape と認可条件が変わっていないか
