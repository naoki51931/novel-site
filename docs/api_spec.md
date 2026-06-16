# API仕様書

- 生成元: FastAPI OpenAPI schema (`app.openapi()`)
- OpenAPI URL設定: `/api/openapi.json`
- 補完元: `backend/app/main.py`, `backend/app/routers/`, `backend/app/features/*_routes.py`, 関連 service source
- 注意: OpenAPI だけでは判定できない認証要否・主なエラーは route / service 実装から補完

## 認証 / OAuth

### `POST /api/auth/login`

- HTTPメソッド: `POST`
- パス: `/api/auth/login`
- 認証要否: 不要
- 概要: Login
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 401 Unauthorized, 422 Validation Error

### `POST /api/auth/login-with-email-code`

- HTTPメソッド: `POST`
- パス: `/api/auth/login-with-email-code`
- 認証要否: 不要
- 概要: Login With Email Code
- リクエスト例:
```json
{
  "email": "user@example.com",
  "code": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/auth/login/start`

- HTTPメソッド: `POST`
- パス: `/api/auth/login/start`
- 認証要否: 不要
- 概要: Login Start
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 401 Unauthorized, 422 Validation Error

### `POST /api/auth/login/verify`

- HTTPメソッド: `POST`
- パス: `/api/auth/login/verify`
- 認証要否: 不要
- 概要: Login Verify
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/auth/oauth/{provider}/callback`

- HTTPメソッド: `GET`
- パス: `/api/auth/oauth/{provider}/callback`
- 認証要否: 不要
- 概要: Oauth Callback
- リクエスト例:
```json
{
  "provider": "string",
  "code": "string",
  "state": "string",
  "oauth_token": "string",
  "oauth_verifier": "string",
  "error": "string",
  "error_description": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `GET /api/auth/oauth/{provider}/start`

- HTTPメソッド: `GET`
- パス: `/api/auth/oauth/{provider}/start`
- 認証要否: 不要
- 概要: Oauth Start
- リクエスト例:
```json
{
  "provider": "string",
  "redirect": "string",
  "client": "string",
  "direct": 0
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `POST /api/auth/password-reset/confirm`

- HTTPメソッド: `POST`
- パス: `/api/auth/password-reset/confirm`
- 認証要否: 不要
- 概要: Password Reset Confirm
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/auth/password-reset/request`

- HTTPメソッド: `POST`
- パス: `/api/auth/password-reset/request`
- 認証要否: 不要
- 概要: Password Reset Request
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/auth/register`

- HTTPメソッド: `POST`
- パス: `/api/auth/register`
- 認証要否: 不要
- 概要: Register User
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/auth/register/email/start`

- HTTPメソッド: `POST`
- パス: `/api/auth/register/email/start`
- 認証要否: 不要
- 概要: Start Register Email Verification
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `POST /api/auth/request-email-code`

- HTTPメソッド: `POST`
- パス: `/api/auth/request-email-code`
- 認証要否: 不要
- 概要: Request Email Code
- リクエスト例:
```json
{
  "email": "user@example.com"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/mobile-push/register`

- HTTPメソッド: `POST`
- パス: `/api/mobile-push/register`
- 認証要否: 必須
- 概要: Register Mobile Push Token
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/mobile-push/unregister`

- HTTPメソッド: `POST`
- パス: `/api/mobile-push/unregister`
- 認証要否: 必須
- 概要: Unregister Mobile Push Token
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/push/debug`

- HTTPメソッド: `POST`
- パス: `/api/push/debug`
- 認証要否: 必須
- 概要: Push Debug Log
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/push/public_key`

- HTTPメソッド: `GET`
- パス: `/api/push/public_key`
- 認証要否: 不要
- 概要: Get Push Public Key
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/push/subscribe`

- HTTPメソッド: `POST`
- パス: `/api/push/subscribe`
- 認証要否: 必須
- 概要: Subscribe Push Notifications
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/push/unsubscribe`

- HTTPメソッド: `POST`
- パス: `/api/push/unsubscribe`
- 認証要否: 必須
- 概要: Unsubscribe Push Notifications
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

## 公開小説 / 作者 / 検索

### `GET /api/authors/{author_id}`

- HTTPメソッド: `GET`
- パス: `/api/authors/{author_id}`
- 認証要否: 不要
- 概要: Read Public Author
- リクエスト例:
```json
{
  "author_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/authors/{author_id}/favorite-tags`

- HTTPメソッド: `GET`
- パス: `/api/authors/{author_id}/favorite-tags`
- 認証要否: 必須
- 概要: Get Author Favorite Tags
- リクエスト例:
```json
{
  "author_id": 1,
  "limit": 12
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/authors/{author_id}/novels`

- HTTPメソッド: `GET`
- パス: `/api/authors/{author_id}/novels`
- 認証要否: 不要
- 概要: List Public Author Novels
- リクエスト例:
```json
{
  "author_id": 1,
  "sort": "latest"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/authors/{author_id}/stats`

- HTTPメソッド: `GET`
- パス: `/api/authors/{author_id}/stats`
- 認証要否: 必須
- 概要: Get Author Stats
- リクエスト例:
```json
{
  "author_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/contact/messages`

- HTTPメソッド: `POST`
- パス: `/api/contact/messages`
- 認証要否: 任意
- 概要: Public Create Contact Message
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/me`

- HTTPメソッド: `GET`
- パス: `/api/me`
- 認証要否: 必須
- 概要: Read Me
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/me/ai/chat/favorites`

- HTTPメソッド: `GET`
- パス: `/api/me/ai/chat/favorites`
- 認証要否: 必須
- 概要: List My Ai Chat Favorites
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/me/ai/chat/usage-history`

- HTTPメソッド: `GET`
- パス: `/api/me/ai/chat/usage-history`
- 認証要否: 必須
- 概要: List My Ai Chat Usage History
- リクエスト例:
```json
{
  "limit": 50
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/me/analytics/novels`

- HTTPメソッド: `GET`
- パス: `/api/me/analytics/novels`
- 認証要否: 必須
- 概要: List My Novel Analytics
- リクエスト例:
```json
{
  "month": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/me/analytics/novels/{novel_id}`

- HTTPメソッド: `GET`
- パス: `/api/me/analytics/novels/{novel_id}`
- 認証要否: 必須
- 概要: Read My Novel Analytics
- リクエスト例:
```json
{
  "novel_id": 1,
  "month": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/me/favorites`

- HTTPメソッド: `GET`
- パス: `/api/me/favorites`
- 認証要否: 必須
- 概要: List My Favorites
- リクエスト例:
```json
{
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/me/scheduled-episodes`

- HTTPメソッド: `GET`
- パス: `/api/me/scheduled-episodes`
- 認証要否: 必須
- 概要: List My Scheduled Episodes
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/me/tag-follows`

- HTTPメソッド: `GET`
- パス: `/api/me/tag-follows`
- 認証要否: 必須
- 概要: List My Tag Follows
- リクエスト例:
```json
{
  "limit": 100
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/me/view-history/ai-public-chats`

- HTTPメソッド: `GET`
- パス: `/api/me/view-history/ai-public-chats`
- 認証要否: 必須
- 概要: List My Public Ai Chat View History
- リクエスト例:
```json
{
  "limit": 50
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/me/view-history/novels`

- HTTPメソッド: `GET`
- パス: `/api/me/view-history/novels`
- 認証要否: 必須
- 概要: List My Novel View History
- リクエスト例:
```json
{
  "limit": 50,
  "offset": 0
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/me/view-history/record`

- HTTPメソッド: `POST`
- パス: `/api/me/view-history/record`
- 認証要否: 必須
- 概要: Record My View History
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/notifications`

- HTTPメソッド: `GET`
- パス: `/api/notifications`
- 認証要否: 必須
- 概要: List Notifications
- リクエスト例:
```json
{
  "limit": 50,
  "offset": 0,
  "unread_only": false,
  "group": "all",
  "notif_type": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/notifications/counts`

- HTTPメソッド: `GET`
- パス: `/api/notifications/counts`
- 認証要否: 必須
- 概要: Notification Counts
- リクエスト例:
```json
{
  "unread_only": false
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/notifications/read_all`

- HTTPメソッド: `POST`
- パス: `/api/notifications/read_all`
- 認証要否: 必須
- 概要: Mark All Notifications Read
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/notifications/unread_count`

- HTTPメソッド: `GET`
- パス: `/api/notifications/unread_count`
- 認証要否: 必須
- 概要: Unread Notification Count
- リクエスト例:
```json
{
  "group": "all"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/notifications/{notification_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/notifications/{notification_id}`
- 認証要否: 必須
- 概要: Delete Notification
- リクエスト例:
```json
{
  "notification_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/notifications/{notification_id}/read`

- HTTPメソッド: `POST`
- パス: `/api/notifications/{notification_id}/read`
- 認証要否: 必須
- 概要: Mark Notification Read
- リクエスト例:
```json
{
  "notification_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/public/novels`

- HTTPメソッド: `GET`
- パス: `/api/public/novels`
- 認証要否: 必須
- 概要: List Public Novels
- リクエスト例:
```json
{
  "q": "string",
  "exclude": "string",
  "tag": "string",
  "sort": "new",
  "age_limit": "string",
  "creative_type": "string",
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/public/users/{username}`

- HTTPメソッド: `GET`
- パス: `/api/public/users/{username}`
- 認証要否: 不要
- 概要: Read Public User
- リクエスト例:
```json
{
  "username": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/public/users/{username}/favorites`

- HTTPメソッド: `GET`
- パス: `/api/public/users/{username}/favorites`
- 認証要否: 必須
- 概要: List Public User Favorites
- リクエスト例:
```json
{
  "username": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/public/users/{username}/novels`

- HTTPメソッド: `GET`
- パス: `/api/public/users/{username}/novels`
- 認証要否: 必須
- 概要: List Public User Novels
- リクエスト例:
```json
{
  "username": "string",
  "sort": "latest"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/search/tags`

- HTTPメソッド: `GET`
- パス: `/api/search/tags`
- 認証要否: 不要
- 概要: Search Public Tags
- リクエスト例:
```json
{
  "q": "string",
  "limit": 8
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/search/users`

- HTTPメソッド: `GET`
- パス: `/api/search/users`
- 認証要否: 不要
- 概要: Search Public Users
- リクエスト例:
```json
{
  "q": "string",
  "limit": 8
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/seo-pages/{slug}`

- HTTPメソッド: `GET`
- パス: `/api/seo-pages/{slug}`
- 認証要否: 不要
- 概要: Read Public Seo Page
- リクエスト例:
```json
{
  "slug": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/users/me`

- HTTPメソッド: `GET`
- パス: `/api/users/me`
- 認証要否: 必須
- 概要: Read Profile
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 401 Unauthorized

### `PUT /api/users/me`

- HTTPメソッド: `PUT`
- パス: `/api/users/me`
- 認証要否: 必須
- 概要: Update Profile
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `DELETE /api/users/{user_id}/follow`

- HTTPメソッド: `DELETE`
- パス: `/api/users/{user_id}/follow`
- 認証要否: 必須
- 概要: Unfollow User
- リクエスト例:
```json
{
  "user_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/users/{user_id}/follow`

- HTTPメソッド: `POST`
- パス: `/api/users/{user_id}/follow`
- 認証要否: 必須
- 概要: Follow User
- リクエスト例:
```json
{
  "user_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/users/{user_id}/follow-status`

- HTTPメソッド: `GET`
- パス: `/api/users/{user_id}/follow-status`
- 認証要否: 必須
- 概要: Get Follow Status
- リクエスト例:
```json
{
  "user_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/users/{user_id}/followers`

- HTTPメソッド: `GET`
- パス: `/api/users/{user_id}/followers`
- 認証要否: 必須
- 概要: List Followers
- リクエスト例:
```json
{
  "user_id": 1,
  "limit": 50,
  "offset": 0
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/users/{user_id}/following`

- HTTPメソッド: `GET`
- パス: `/api/users/{user_id}/following`
- 認証要否: 必須
- 概要: List Following
- リクエスト例:
```json
{
  "user_id": 1,
  "limit": 50,
  "offset": 0
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /ogp/novel/{novel_id}.png`

- HTTPメソッド: `GET`
- パス: `/ogp/novel/{novel_id}.png`
- 認証要否: 不要
- 概要: Novel Og Image
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /prerender/episodes/{episode_id}`

- HTTPメソッド: `GET`
- パス: `/prerender/episodes/{episode_id}`
- 認証要否: 不要
- 概要: Prerender Episode Page
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /prerender/novels/{novel_id}`

- HTTPメソッド: `GET`
- パス: `/prerender/novels/{novel_id}`
- 認証要否: 不要
- 概要: Prerender Novel Page
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /robots.txt`

- HTTPメソッド: `GET`
- パス: `/robots.txt`
- 認証要否: 不要
- 概要: Robots Txt
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /share/episodes/{episode_id}`

- HTTPメソッド: `GET`
- パス: `/share/episodes/{episode_id}`
- 認証要否: 不要
- 概要: Share Episode Page
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /share/episodes/{episode_id}/og-image.png`

- HTTPメソッド: `GET`
- パス: `/share/episodes/{episode_id}/og-image.png`
- 認証要否: 不要
- 概要: Share Episode Og Image
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `GET /sitemap-authors.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-authors.xml`
- 認証要否: 不要
- 概要: Sitemap Authors Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap-episodes.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-episodes.xml`
- 認証要否: 不要
- 概要: Sitemap Episodes Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap-index.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-index.xml`
- 認証要否: 不要
- 概要: Sitemap Index Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap-main.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-main.xml`
- 認証要否: 不要
- 概要: Sitemap Main Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap-novels.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-novels.xml`
- 認証要否: 不要
- 概要: Sitemap Novels Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap-seo-pages.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-seo-pages.xml`
- 認証要否: 不要
- 概要: Sitemap Seo Pages Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap-static.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-static.xml`
- 認証要否: 不要
- 概要: Sitemap Static Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap-tags.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap-tags.xml`
- 認証要否: 不要
- 概要: Sitemap Tags Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /sitemap.xml`

- HTTPメソッド: `GET`
- パス: `/sitemap.xml`
- 認証要否: 不要
- 概要: Sitemap Xml
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /{indexnow_key_file}.txt`

- HTTPメソッド: `GET`
- パス: `/{indexnow_key_file}.txt`
- 認証要否: 不要
- 概要: Indexnow Key File
- リクエスト例:
```json
{
  "indexnow_key_file": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

## 小説 / エピソード / タグ / シリーズ

### `GET /api/author/dashboard`

- HTTPメソッド: `GET`
- パス: `/api/author/dashboard`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Get Author Dashboard
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/author/dashboard/novels/{novel_id}/daily`

- HTTPメソッド: `GET`
- パス: `/api/author/dashboard/novels/{novel_id}/daily`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Get Author Novel Daily Metrics
- リクエスト例:
```json
{
  "novel_id": 1,
  "days": 30
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/author/dashboard/top-novels`

- HTTPメソッド: `GET`
- パス: `/api/author/dashboard/top-novels`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Get Author Top Novels
- リクエスト例:
```json
{
  "limit": 10,
  "sort": "views"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/covers/generate`

- HTTPメソッド: `POST`
- パス: `/api/covers/generate`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Generate Cover
- リクエスト例:
```json
{
  "novel_id": 1,
  "title": "",
  "catch_copy": "",
  "genre": "string",
  "mood": "string",
  "color_theme": "string",
  "character_count": 1,
  "extra_prompt": ""
}
```
- レスポンス例:
```json
{
  "id": 1,
  "status": "string",
  "image_url": "string",
  "image_path": "string",
  "prompt_used": "string",
  "model": "string",
  "created_at": "2026-01-01T00:00:00Z"
}
```
- 主なエラー: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `GET /api/covers/history`

- HTTPメソッド: `GET`
- パス: `/api/covers/history`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Get Cover History
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
[
  {
    "id": 1,
    "novel_id": 1,
    "status": "string",
    "image_path": "string",
    "image_url": "string",
    "prompt": "string",
    "model": "string",
    "error_message": "string",
    "created_at": "2026-01-01T00:00:00Z"
  }
]
```
- 主なエラー: 422 Validation Error

### `DELETE /api/covers/history/{cover_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/covers/history/{cover_id}`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Delete Cover History Item
- リクエスト例:
```json
{
  "cover_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `DELETE /api/episodes/{episode_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/episodes/{episode_id}`
- 認証要否: 必須
- 概要: Delete Episode
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/episodes/{episode_id}`

- HTTPメソッド: `GET`
- パス: `/api/episodes/{episode_id}`
- 認証要否: 不要
- 概要: Get Episode
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `PUT /api/episodes/{episode_id}`

- HTTPメソッド: `PUT`
- パス: `/api/episodes/{episode_id}`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Update Episode
- リクエスト例:
```json
{
  "params": {
    "episode_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/cover-image`

- HTTPメソッド: `DELETE`
- パス: `/api/episodes/{episode_id}/cover-image`
- 認証要否: 必須
- 概要: Delete Episode Cover Image
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 422 Validation Error

### `POST /api/episodes/{episode_id}/cover-image`

- HTTPメソッド: `POST`
- パス: `/api/episodes/{episode_id}/cover-image`
- 認証要否: 必須
- 概要: Upload Episode Cover Image
- リクエスト例:
```json
{
  "params": {
    "episode_id": 1
  },
  "form": {
    "file": "<binary>"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `GET /api/episodes/{episode_id}/edit`

- HTTPメソッド: `GET`
- パス: `/api/episodes/{episode_id}/edit`
- 認証要否: 必須
- 概要: Get Episode For Edit
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/illusts`

- HTTPメソッド: `POST`
- パス: `/api/episodes/{episode_id}/illusts`
- 認証要否: 必須
- 概要: Upload Episode Illust
- リクエスト例:
```json
{
  "params": {
    "episode_id": 1
  },
  "form": {
    "file": "<binary>",
    "caption": "",
    "illust_tag": "",
    "meta_tags": ""
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/illusts/{illust_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/episodes/{episode_id}/illusts/{illust_id}`
- 認証要否: 必須
- 概要: Delete Episode Illust
- リクエスト例:
```json
{
  "episode_id": 1,
  "illust_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/like`

- HTTPメソッド: `DELETE`
- パス: `/api/episodes/{episode_id}/like`
- 認証要否: 必須
- 概要: Unlike Episode
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/like`

- HTTPメソッド: `POST`
- パス: `/api/episodes/{episode_id}/like`
- 認証要否: 必須
- 概要: Like Episode
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/title_candidates`

- HTTPメソッド: `POST`
- パス: `/api/episodes/{episode_id}/title_candidates`
- 認証要否: 必須
- 概要: Generate Episode Title Candidates
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/episodes/{episode_id}/translations/{lang}`

- HTTPメソッド: `GET`
- パス: `/api/episodes/{episode_id}/translations/{lang}`
- 認証要否: 不要
- 概要: Get Episode Translation
- リクエスト例:
```json
{
  "episode_id": 1,
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/unschedule`

- HTTPメソッド: `POST`
- パス: `/api/episodes/{episode_id}/unschedule`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Unschedule Episode
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 422 Validation Error

### `GET /api/novels`

- HTTPメソッド: `GET`
- パス: `/api/novels`
- 認証要否: 必須
- 概要: List Novels
- リクエスト例:
```json
{
  "mine": false,
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/novels`

- HTTPメソッド: `POST`
- パス: `/api/novels`
- 認証要否: 必須
- 概要: Create Novel
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/novels/`

- HTTPメソッド: `POST`
- パス: `/api/novels/`
- 認証要否: 必須
- 概要: Create Novel
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/novels/{novel_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/novels/{novel_id}`
- 認証要否: 必須
- 概要: Delete Novel
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/novels/{novel_id}`

- HTTPメソッド: `GET`
- パス: `/api/novels/{novel_id}`
- 認証要否: 不要
- 概要: Get Novel Detail
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `PUT /api/novels/{novel_id}`

- HTTPメソッド: `PUT`
- パス: `/api/novels/{novel_id}`
- 認証要否: 必須
- 概要: Update Novel
- リクエスト例:
```json
{
  "params": {
    "novel_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/novels/{novel_id}/cover`

- HTTPメソッド: `DELETE`
- パス: `/api/novels/{novel_id}/cover`
- 認証要否: 必須
- 概要: Delete Novel Cover
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/novels/{novel_id}/cover`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/cover`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Set Novel Cover
- リクエスト例:
```json
{
  "params": {
    "novel_id": 1
  },
  "body": {
    "image_path": "string"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `POST /api/novels/{novel_id}/cover-image`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/cover-image`
- 認証要否: 必須
- 概要: Upload Novel Cover Image
- リクエスト例:
```json
{
  "params": {
    "novel_id": 1
  },
  "form": {
    "file": "<binary>"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/novels/{novel_id}/episodes`

- HTTPメソッド: `GET`
- パス: `/api/novels/{novel_id}/episodes`
- 認証要否: 不要
- 概要: List Episodes
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/novels/{novel_id}/episodes`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/episodes`
- 認証要否: 必須 (一部プレミアム条件あり)
- 概要: Create Episode
- リクエスト例:
```json
{
  "params": {
    "novel_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/novels/{novel_id}/favorite`

- HTTPメソッド: `DELETE`
- パス: `/api/novels/{novel_id}/favorite`
- 認証要否: 必須
- 概要: Unfavorite Novel
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/novels/{novel_id}/favorite`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/favorite`
- 認証要否: 必須
- 概要: Favorite Novel
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/novels/{novel_id}/like`

- HTTPメソッド: `DELETE`
- パス: `/api/novels/{novel_id}/like`
- 認証要否: 必須
- 概要: Unlike Novel
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/novels/{novel_id}/like`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/like`
- 認証要否: 必須
- 概要: Like Novel
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/novels/{novel_id}/summary_candidates`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/summary_candidates`
- 認証要否: 必須
- 概要: Generate Novel Summary Candidates
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `POST /api/novels/{novel_id}/tag_candidates`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/tag_candidates`
- 認証要否: 必須
- 概要: Generate Novel Tag Candidates
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `POST /api/novels/{novel_id}/title_candidates`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/title_candidates`
- 認証要否: 必須
- 概要: Generate Novel Title Candidates
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/novels/{novel_id}/translations/{lang}`

- HTTPメソッド: `GET`
- パス: `/api/novels/{novel_id}/translations/{lang}`
- 認証要否: 不要
- 概要: Get Novel Translation
- リクエスト例:
```json
{
  "novel_id": 1,
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/series`

- HTTPメソッド: `GET`
- パス: `/api/series`
- 認証要否: 不要
- 概要: List Series Overview
- リクエスト例:
```json
{
  "q": "string",
  "limit": 30
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/series/{series_name}/novels`

- HTTPメソッド: `GET`
- パス: `/api/series/{series_name}/novels`
- 認証要否: 不要
- 概要: List Series Novels
- リクエスト例:
```json
{
  "series_name": "string",
  "limit": 60
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/tags`

- HTTPメソッド: `GET`
- パス: `/api/tags`
- 認証要否: 不要
- 概要: List Tags
- リクエスト例:
```json
{
  "limit": 100
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/tags/{tag_name}`

- HTTPメソッド: `GET`
- パス: `/api/tags/{tag_name}`
- 認証要否: 不要
- 概要: Read Tag Detail
- リクエスト例:
```json
{
  "tag_name": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `DELETE /api/tags/{tag_name}/follow`

- HTTPメソッド: `DELETE`
- パス: `/api/tags/{tag_name}/follow`
- 認証要否: 必須
- 概要: Unfollow Tag
- リクエスト例:
```json
{
  "tag_name": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/tags/{tag_name}/follow`

- HTTPメソッド: `POST`
- パス: `/api/tags/{tag_name}/follow`
- 認証要否: 必須
- 概要: Follow Tag
- リクエスト例:
```json
{
  "tag_name": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/tags/{tag_name}/follow-status`

- HTTPメソッド: `GET`
- パス: `/api/tags/{tag_name}/follow-status`
- 認証要否: 必須
- 概要: Read Tag Follow Status
- リクエスト例:
```json
{
  "tag_name": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/tags/{tag_name}/novels`

- HTTPメソッド: `GET`
- パス: `/api/tags/{tag_name}/novels`
- 認証要否: 不要
- 概要: List Tag Novels
- リクエスト例:
```json
{
  "tag_name": "string",
  "sort": "popular",
  "limit": 60,
  "offset": 0
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/tags/{tag_name}/related`

- HTTPメソッド: `GET`
- パス: `/api/tags/{tag_name}/related`
- 認証要否: 不要
- 概要: List Related Tags
- リクエスト例:
```json
{
  "tag_name": "string",
  "limit": 12
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

## フィード / レコメンド

### `GET /api/feed/following`

- HTTPメソッド: `GET`
- パス: `/api/feed/following`
- 認証要否: 必須
- 概要: List Following Feed
- リクエスト例:
```json
{
  "limit": 20
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/feed/following-tags`

- HTTPメソッド: `GET`
- パス: `/api/feed/following-tags`
- 認証要否: 必須
- 概要: List Following Tags Feed
- リクエスト例:
```json
{
  "limit": 20
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/feed/history`

- HTTPメソッド: `GET`
- パス: `/api/feed/history`
- 認証要否: 必須
- 概要: List History Feed
- リクエスト例:
```json
{
  "limit": 12
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/feed/new`

- HTTPメソッド: `GET`
- パス: `/api/feed/new`
- 認証要否: 任意
- 概要: List New Feed
- リクエスト例:
```json
{
  "limit": 20,
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/feed/pickups`

- HTTPメソッド: `GET`
- パス: `/api/feed/pickups`
- 認証要否: 必須
- 概要: List Pickups Feed
- リクエスト例:
```json
{
  "limit": 8
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/feed/recommended`

- HTTPメソッド: `GET`
- パス: `/api/feed/recommended`
- 認証要否: 任意
- 概要: List Recommended Feed
- リクエスト例:
```json
{
  "limit": 12,
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/feed/trending`

- HTTPメソッド: `GET`
- パス: `/api/feed/trending`
- 認証要否: 任意
- 概要: List Trending Feed
- リクエスト例:
```json
{
  "limit": 20,
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/public/novels/ranking`

- HTTPメソッド: `GET`
- パス: `/api/public/novels/ranking`
- 認証要否: 必須
- 概要: List Public Novel Rankings
- リクエスト例:
```json
{
  "sort": "likes",
  "period": "weekly",
  "limit": 10,
  "q": "string",
  "exclude": "string",
  "tag": "string",
  "creative_type": "string",
  "age_limit": "string",
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `GET /api/public/novels/recommended`

- HTTPメソッド: `GET`
- パス: `/api/public/novels/recommended`
- 認証要否: 任意
- 概要: List Recommended Public Novels
- リクエスト例:
```json
{
  "limit": 12,
  "lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/trending-tags`

- HTTPメソッド: `GET`
- パス: `/api/trending-tags`
- 認証要否: 不要
- 概要: List Trending Tags
- リクエスト例:
```json
{
  "days": 7,
  "limit": 20
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

## コメント / DM / 掲示板

### `GET /api/board/posts`

- HTTPメソッド: `GET`
- パス: `/api/board/posts`
- 認証要否: 不要
- 概要: List Board Posts
- リクエスト例:
```json
{
  "limit": 1000
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/board/posts`

- HTTPメソッド: `POST`
- パス: `/api/board/posts`
- 認証要否: 任意
- 概要: Create Board Post
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `POST /api/dms`

- HTTPメソッド: `POST`
- パス: `/api/dms`
- 認証要否: 必須
- 概要: Create Dm Thread
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/dms/{thread_id}`

- HTTPメソッド: `GET`
- パス: `/api/dms/{thread_id}`
- 認証要否: 必須
- 概要: Read Dm Thread
- リクエスト例:
```json
{
  "thread_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `POST /api/dms/{thread_id}/messages`

- HTTPメソッド: `POST`
- パス: `/api/dms/{thread_id}/messages`
- 認証要否: 必須
- 概要: Create Dm Message
- リクエスト例:
```json
{
  "params": {
    "thread_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/episodes/{episode_id}/comments`

- HTTPメソッド: `GET`
- パス: `/api/episodes/{episode_id}/comments`
- 認証要否: 不要
- 概要: Get Episode Comments
- リクエスト例:
```json
{
  "episode_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/episodes/{episode_id}/comments`

- HTTPメソッド: `POST`
- パス: `/api/episodes/{episode_id}/comments`
- 認証要否: 必須
- 概要: Post Episode Comment
- リクエスト例:
```json
{
  "params": {
    "episode_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/comments/{comment_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/episodes/{episode_id}/comments/{comment_id}`
- 認証要否: 必須
- 概要: Delete Episode Comment
- リクエスト例:
```json
{
  "episode_id": 1,
  "comment_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/novels/{novel_id}/comments`

- HTTPメソッド: `GET`
- パス: `/api/novels/{novel_id}/comments`
- 認証要否: 不要
- 概要: Get Comments
- リクエスト例:
```json
{
  "novel_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/novels/{novel_id}/comments`

- HTTPメソッド: `POST`
- パス: `/api/novels/{novel_id}/comments`
- 認証要否: 必須
- 概要: Post Comment
- リクエスト例:
```json
{
  "params": {
    "novel_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `DELETE /api/novels/{novel_id}/comments/{comment_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/novels/{novel_id}/comments/{comment_id}`
- 認証要否: 必須
- 概要: Delete Comment
- リクエスト例:
```json
{
  "novel_id": 1,
  "comment_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 403 Forbidden, 404 Not Found, 422 Validation Error

## 支援 / Stripe / Membership / Payout

### `GET /api/authors/me/balance`

- HTTPメソッド: `GET`
- パス: `/api/authors/me/balance`
- 認証要否: 必須
- 概要: Get Author Balance
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/authors/me/payout_profile`

- HTTPメソッド: `POST`
- パス: `/api/authors/me/payout_profile`
- 認証要否: 必須
- 概要: Update Payout Profile
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/authors/me/support_plans`

- HTTPメソッド: `GET`
- パス: `/api/authors/me/support_plans`
- 認証要否: 必須
- 概要: List My Support Plans
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/authors/me/support_plans`

- HTTPメソッド: `POST`
- パス: `/api/authors/me/support_plans`
- 認証要否: 必須
- 概要: Create Support Plan
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 409 Conflict, 422 Validation Error

### `PATCH /api/authors/me/support_plans/{plan_id}`

- HTTPメソッド: `PATCH`
- パス: `/api/authors/me/support_plans/{plan_id}`
- 認証要否: 必須
- 概要: Update Support Plan
- リクエスト例:
```json
{
  "params": {
    "plan_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 409 Conflict, 422 Validation Error

### `POST /api/authors/me/support_plans/{plan_id}/activate`

- HTTPメソッド: `POST`
- パス: `/api/authors/me/support_plans/{plan_id}/activate`
- 認証要否: 必須
- 概要: Activate Support Plan
- リクエスト例:
```json
{
  "plan_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 409 Conflict, 422 Validation Error

### `POST /api/authors/me/support_plans/{plan_id}/deactivate`

- HTTPメソッド: `POST`
- パス: `/api/authors/me/support_plans/{plan_id}/deactivate`
- 認証要否: 必須
- 概要: Deactivate Support Plan
- リクエスト例:
```json
{
  "plan_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/memberships/checkout`

- HTTPメソッド: `POST`
- パス: `/api/memberships/checkout`
- 認証要否: 必須
- 概要: Memberships Checkout
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `POST /api/stripe/create-checkout-session`

- HTTPメソッド: `POST`
- パス: `/api/stripe/create-checkout-session`
- 認証要否: 必須
- 概要: Stripe Checkout
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 500 Internal Server Error

### `POST /api/stripe/webhook`

- HTTPメソッド: `POST`
- パス: `/api/stripe/webhook`
- 認証要否: 不要 (Stripe署名必須)
- 概要: Stripe Webhook
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `GET /api/support_plans`

- HTTPメソッド: `GET`
- パス: `/api/support_plans`
- 認証要否: 不要
- 概要: List Support Plans
- リクエスト例:
```json
{
  "author_user_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/supports/checkout`

- HTTPメソッド: `POST`
- パス: `/api/supports/checkout`
- 認証要否: 任意
- 概要: Supports Checkout
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

## AI小説 / AIチャット / 翻訳

### `POST /api/ai/character_terms`

- HTTPメソッド: `POST`
- パス: `/api/ai/character_terms`
- 認証要否: 不要
- 概要: Extract Ai Character Terms
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat`
- 認証要否: 不要
- 概要: Ai Chat
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/chat/access`

- HTTPメソッド: `GET`
- パス: `/api/ai/chat/access`
- 認証要否: 不要
- 概要: Get Ai Chat Access Status
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/chat/addon/checkout`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/addon/checkout`
- 認証要否: 必須
- 概要: Create Ai Chat Addon Checkout
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 402 Payment Required, 422 Validation Error, 500 Internal Server Error

### `POST /api/ai/chat/auto_continue`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/auto_continue`
- 認証要否: 不要
- 概要: Ai Chat Auto Continue
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/character/anime_title_candidates`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/character/anime_title_candidates`
- 認証要否: 不要
- 概要: Ai Chat Character Anime Title Candidates
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/character/augment`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/character/augment`
- 認証要否: 不要
- 概要: Augment Ai Chat Character
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/chat/characters`

- HTTPメソッド: `GET`
- パス: `/api/ai/chat/characters`
- 認証要否: 不要
- 概要: List Ai Chat Characters
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/chat/characters`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/characters`
- 認証要否: 不要
- 概要: Create Ai Chat Character
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/ai/chat/characters/{character_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/ai/chat/characters/{character_id}`
- 認証要否: 不要
- 概要: Delete Ai Chat Character
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `PUT /api/ai/chat/characters/{character_id}`

- HTTPメソッド: `PUT`
- パス: `/api/ai/chat/characters/{character_id}`
- 認証要否: 不要
- 概要: Update Ai Chat Character
- リクエスト例:
```json
{
  "params": {
    "character_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/chat/characters/{character_id}/engagement_summary`

- HTTPメソッド: `GET`
- パス: `/api/ai/chat/characters/{character_id}/engagement_summary`
- 認証要否: 不要
- 概要: Get Ai Chat Engagement Summary
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/characters/{character_id}/image`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/characters/{character_id}/image`
- 認証要否: 不要
- 概要: Upload Ai Chat Character Image
- リクエスト例:
```json
{
  "params": {
    "character_id": 1
  },
  "form": {
    "file": "<binary>"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/chat/characters/{character_id}/latest_prompt_preview`

- HTTPメソッド: `GET`
- パス: `/api/ai/chat/characters/{character_id}/latest_prompt_preview`
- 認証要否: 不要
- 概要: Get Ai Chat Latest Prompt Preview
- リクエスト例:
```json
{
  "character_id": 1,
  "r18": false
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/chat/characters/{character_id}/messages`

- HTTPメソッド: `GET`
- パス: `/api/ai/chat/characters/{character_id}/messages`
- 認証要否: 不要
- 概要: List Ai Chat Messages
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/characters/{character_id}/messages/images`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/characters/{character_id}/messages/images`
- 認証要否: 不要
- 概要: Upload Ai Chat Message Images
- リクエスト例:
```json
{
  "params": {
    "character_id": 1
  },
  "form": {
    "files": [
      "<binary>"
    ]
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/characters/{character_id}/messages/import`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/characters/{character_id}/messages/import`
- 認証要否: 不要
- 概要: Import Ai Chat Messages
- リクエスト例:
```json
{
  "params": {
    "character_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/ai/chat/characters/{character_id}/messages/{message_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/ai/chat/characters/{character_id}/messages/{message_id}`
- 認証要否: 不要
- 概要: Delete Ai Chat Messages From Point
- リクエスト例:
```json
{
  "character_id": 1,
  "message_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/ai/chat/characters/{character_id}/messages/{message_id}/images/{image_index}`

- HTTPメソッド: `DELETE`
- パス: `/api/ai/chat/characters/{character_id}/messages/{message_id}/images/{image_index}`
- 認証要否: 不要
- 概要: Delete Ai Chat Message Image
- リクエスト例:
```json
{
  "character_id": 1,
  "message_id": 1,
  "image_index": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `PATCH /api/ai/chat/characters/{character_id}/publish`

- HTTPメソッド: `PATCH`
- パス: `/api/ai/chat/characters/{character_id}/publish`
- 認証要否: 不要
- 概要: Publish Ai Chat Character
- リクエスト例:
```json
{
  "params": {
    "character_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/generate_image`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/generate_image`
- 認証要否: 不要
- 概要: Ai Chat Generate Image
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/next_user_lines`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/next_user_lines`
- 認証要否: 不要
- 概要: Ai Chat Next User Lines
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/chat/public/characters`

- HTTPメソッド: `GET`
- パス: `/api/ai/chat/public/characters`
- 認証要否: 不要
- 概要: List Public Ai Chat Characters
- リクエスト例:
```json
{
  "q": "",
  "limit": 20,
  "offset": 0
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/chat/public/characters/{character_id}`

- HTTPメソッド: `GET`
- パス: `/api/ai/chat/public/characters/{character_id}`
- 認証要否: 不要
- 概要: Get Public Ai Chat Character Detail
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
{
  "id": 1,
  "name": "string",
  "personality": "string",
  "image_url": "string",
  "is_r18": false,
  "author_username": "string",
  "published_at": "string",
  "like_count": 0,
  "favorite_count": 0,
  "is_liked": false,
  "is_favorited": false,
  "messages": [
    {
      "id": 1,
      "role": "user",
      "mode": "say",
      "is_auto_dialogue": false,
      "content": "string",
      "speaker_name": "string",
      "character_name": "string",
      "message_owner_username": "string",
      "created_at": "string"
    }
  ]
}
```
- 主なエラー: 422 Validation Error

### `DELETE /api/ai/chat/public/characters/{character_id}/favorite`

- HTTPメソッド: `DELETE`
- パス: `/api/ai/chat/public/characters/{character_id}/favorite`
- 認証要否: 必須
- 概要: Unfavorite Public Ai Chat Character
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/public/characters/{character_id}/favorite`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/public/characters/{character_id}/favorite`
- 認証要否: 必須
- 概要: Favorite Public Ai Chat Character
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/ai/chat/public/characters/{character_id}/like`

- HTTPメソッド: `DELETE`
- パス: `/api/ai/chat/public/characters/{character_id}/like`
- 認証要否: 必須
- 概要: Unlike Public Ai Chat Character
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/chat/public/characters/{character_id}/like`

- HTTPメソッド: `POST`
- パス: `/api/ai/chat/public/characters/{character_id}/like`
- 認証要否: 必須
- 概要: Like Public Ai Chat Character
- リクエスト例:
```json
{
  "character_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/episodes/assist_candidates`

- HTTPメソッド: `POST`
- パス: `/api/ai/episodes/assist_candidates`
- 認証要否: 不要
- 概要: Generate Episode Assist Candidates
- リクエスト例:
```json
{
  "title": "string",
  "text": "string",
  "tags": [],
  "suggestions_count": 4,
  "model": "string",
  "provider": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/episodes/{episode_id}/continue`

- HTTPメソッド: `POST`
- パス: `/api/ai/episodes/{episode_id}/continue`
- 認証要否: 不要
- 概要: Generate Ai Episode Continue
- リクエスト例:
```json
{
  "params": {
    "episode_id": 1
  },
  "body": {
    "title_hint": "string",
    "genre": "string",
    "characters": "string",
    "tone": "string",
    "length": "medium",
    "prompt": "string",
    "model": "string",
    "provider": "string",
    "r18": false,
    "retry_mode": false,
    "retry_max": 1,
    "chunked_generation_enabled": false,
    "chunked_generation_count": 1,
    "chunked_generation_plans": [
      {
        "example_key": "value"
      }
    ]
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/episodes/{episode_id}/continue_job`

- HTTPメソッド: `POST`
- パス: `/api/ai/episodes/{episode_id}/continue_job`
- 認証要否: 不要
- 概要: Create Ai Episode Continue Job
- リクエスト例:
```json
{
  "params": {
    "episode_id": 1
  },
  "body": {
    "title_hint": "string",
    "genre": "string",
    "characters": "string",
    "tone": "string",
    "length": "medium",
    "prompt": "string",
    "model": "string",
    "provider": "string",
    "r18": false,
    "retry_mode": false,
    "retry_max": 1,
    "chunked_generation_enabled": false,
    "chunked_generation_count": 1,
    "chunked_generation_plans": [
      {
        "example_key": "value"
      }
    ]
  }
}
```
- レスポンス例:
```json
{
  "job_id": 1,
  "status": "string"
}
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/jobs`

- HTTPメソッド: `GET`
- パス: `/api/ai/jobs`
- 認証要否: 管理者必須
- 概要: List All Ai Jobs
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/jobs/kill_all`

- HTTPメソッド: `POST`
- パス: `/api/ai/jobs/kill_all`
- 認証要否: 管理者必須
- 概要: Kill All Ai Jobs
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/jobs/kill_me`

- HTTPメソッド: `POST`
- パス: `/api/ai/jobs/kill_me`
- 認証要否: 必須
- 概要: Kill My Ai Jobs
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/jobs/kill_selected`

- HTTPメソッド: `POST`
- パス: `/api/ai/jobs/kill_selected`
- 認証要否: 管理者必須
- 概要: Kill Selected Ai Jobs
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/jobs/kill_selected_me`

- HTTPメソッド: `POST`
- パス: `/api/ai/jobs/kill_selected_me`
- 認証要否: 必須
- 概要: Kill Selected My Ai Jobs
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/jobs/me`

- HTTPメソッド: `GET`
- パス: `/api/ai/jobs/me`
- 認証要否: 必須
- 概要: List My Ai Jobs
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/ai/jobs/{job_id}`

- HTTPメソッド: `GET`
- パス: `/api/ai/jobs/{job_id}`
- 認証要否: 任意
- 概要: Get Ai Job Status
- リクエスト例:
```json
{
  "job_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/logs/me`

- HTTPメソッド: `GET`
- パス: `/api/ai/logs/me`
- 認証要否: 必須
- 概要: Get My Ai Logs
- リクエスト例:
```json
{
  "limit": 50
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/memory/backfill`

- HTTPメソッド: `POST`
- パス: `/api/ai/memory/backfill`
- 認証要否: 不要
- 概要: Backfill Ai Memory From Logs
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/memory/items`

- HTTPメソッド: `GET`
- パス: `/api/ai/memory/items`
- 認証要否: 不要
- 概要: List Ai Memory Items
- リクエスト例:
```json
{
  "scope": "global",
  "scope_id": 1,
  "include_inactive": false,
  "limit": 50
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/ai/memory/items/{memory_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/ai/memory/items/{memory_id}`
- 認証要否: 不要
- 概要: Delete Ai Memory Item
- リクエスト例:
```json
{
  "memory_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `PATCH /api/ai/memory/items/{memory_id}/deactivate`

- HTTPメソッド: `PATCH`
- パス: `/api/ai/memory/items/{memory_id}/deactivate`
- 認証要否: 不要
- 概要: Deactivate Ai Memory Item
- リクエスト例:
```json
{
  "memory_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/novel/addon/checkout`

- HTTPメソッド: `POST`
- パス: `/api/ai/novel/addon/checkout`
- 認証要否: 必須
- 概要: Create Ai Novel Addon Checkout
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 402 Payment Required, 422 Validation Error, 500 Internal Server Error

### `POST /api/ai/novels/addon/checkout`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/addon/checkout`
- 認証要否: 必須
- 概要: Create Ai Novel Addon Checkout
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 402 Payment Required, 422 Validation Error, 500 Internal Server Error

### `GET /api/ai/novels/auto-fill`

- HTTPメソッド: `GET`
- パス: `/api/ai/novels/auto-fill`
- 認証要否: 不要
- 概要: Auto Fill Ai Novel Inputs
- リクエスト例:
```json
{
  "query": "string",
  "characters": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/novels/auto-fill`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/auto-fill`
- 認証要否: 不要
- 概要: Auto Fill Ai Novel Inputs Post
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/novels/draft`

- HTTPメソッド: `GET`
- パス: `/api/ai/novels/draft`
- 認証要否: 必須
- 概要: Get Ai Novel Draft
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/novels/draft`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/draft`
- 認証要否: 必須
- 概要: Save Ai Novel Draft
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/novels/drafts`

- HTTPメソッド: `GET`
- パス: `/api/ai/novels/drafts`
- 認証要否: 必須
- 概要: List Ai Novel Drafts
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/novels/drafts`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/drafts`
- 認証要否: 必須
- 概要: Create Ai Novel Draft
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/ai/novels/drafts/{draft_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/ai/novels/drafts/{draft_id}`
- 認証要否: 必須
- 概要: Delete Ai Novel Draft
- リクエスト例:
```json
{
  "draft_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/novels/drafts/{draft_id}`

- HTTPメソッド: `GET`
- パス: `/api/ai/novels/drafts/{draft_id}`
- 認証要否: 必須
- 概要: Get Ai Novel Draft Slot
- リクエスト例:
```json
{
  "draft_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `PUT /api/ai/novels/drafts/{draft_id}`

- HTTPメソッド: `PUT`
- パス: `/api/ai/novels/drafts/{draft_id}`
- 認証要否: 必須
- 概要: Update Ai Novel Draft
- リクエスト例:
```json
{
  "params": {
    "draft_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/novels/generate`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/generate`
- 認証要否: 不要
- 概要: Generate Ai Novel
- リクエスト例:
```json
{
  "title_hint": "string",
  "genre": "string",
  "characters": "string",
  "tone": "string",
  "length": "medium",
  "prompt": "string",
  "model": "string",
  "provider": "string",
  "r18": false,
  "retry_mode": false,
  "retry_max": 1,
  "chunked_generation_enabled": false,
  "chunked_generation_count": 1,
  "chunked_generation_plans": [
    {
      "example_key": "value"
    }
  ]
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/novels/generate_job`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/generate_job`
- 認証要否: 不要
- 概要: Create Ai Novel Job
- リクエスト例:
```json
{
  "title_hint": "string",
  "genre": "string",
  "characters": "string",
  "tone": "string",
  "length": "medium",
  "prompt": "string",
  "model": "string",
  "provider": "string",
  "r18": false,
  "retry_mode": false,
  "retry_max": 1,
  "chunked_generation_enabled": false,
  "chunked_generation_count": 1,
  "chunked_generation_plans": [
    {
      "example_key": "value"
    }
  ]
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/ai/novels/remaining`

- HTTPメソッド: `GET`
- パス: `/api/ai/novels/remaining`
- 認証要否: 任意
- 概要: Get Ai Novel Remaining
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/ai/novels/revision-target`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/revision-target`
- 認証要否: 不要
- 概要: Locate Ai Novel Revision Target
- リクエスト例:
```json
{
  "body": "string",
  "comments": [
    "string"
  ],
  "scope": "full",
  "r18": false
}
```
- レスポンス例:
```json
{
  "target_text": "string",
  "start": 1,
  "end": 1,
  "used_weaviate": false,
  "attempted_weaviate": false,
  "fallback_reason": "string",
  "candidate_count": 0
}
```
- 主なエラー: 422 Validation Error

### `POST /api/ai/novels/story-agent`

- HTTPメソッド: `POST`
- パス: `/api/ai/novels/story-agent`
- 認証要否: 任意
- 概要: Generate Story Agent Reply
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error, 502 Bad Gateway

### `POST /api/ai/summary_candidates`

- HTTPメソッド: `POST`
- パス: `/api/ai/summary_candidates`
- 認証要否: 必須
- 概要: Generate Summary Candidates
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/ai/tag_candidates`

- HTTPメソッド: `POST`
- パス: `/api/ai/tag_candidates`
- 認証要否: 必須
- 概要: Generate Tag Candidates
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/ai/title_candidate`

- HTTPメソッド: `POST`
- パス: `/api/ai/title_candidate`
- 認証要否: 必須
- 概要: Generate Title Candidate
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/ai/title_candidates`

- HTTPメソッド: `POST`
- パス: `/api/ai/title_candidates`
- 認証要否: 必須
- 概要: Generate Title Candidates
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/i18n/dictionary/{target_lang}`

- HTTPメソッド: `GET`
- パス: `/api/i18n/dictionary/{target_lang}`
- 認証要否: 不要
- 概要: I18N Dictionary
- リクエスト例:
```json
{
  "target_lang": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/i18n/translate`

- HTTPメソッド: `POST`
- パス: `/api/i18n/translate`
- 認証要否: 不要
- 概要: I18N Translate
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

## 管理 / SEO / Indexing

### `GET /api/admin/ai-chat/token-consumers/timeline`

- HTTPメソッド: `GET`
- パス: `/api/admin/ai-chat/token-consumers/timeline`
- 認証要否: 管理者必須
- 概要: Admin Ai Chat Token Consumers Timeline
- リクエスト例:
```json
{
  "days": 30,
  "limit": 20
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/admin/ai/logs`

- HTTPメソッド: `GET`
- パス: `/api/admin/ai/logs`
- 認証要否: 管理者必須
- 概要: Admin Get Ai Logs
- リクエスト例:
```json
{
  "limit": 200
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/admin/auth/login`

- HTTPメソッド: `POST`
- パス: `/api/admin/auth/login`
- 認証要否: 管理者必須
- 概要: Admin Login
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 401 Unauthorized, 422 Validation Error, 500 Internal Server Error

### `POST /api/admin/auth/logout`

- HTTPメソッド: `POST`
- パス: `/api/admin/auth/logout`
- 認証要否: 管理者必須
- 概要: Admin Logout
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/admin/auth/me`

- HTTPメソッド: `GET`
- パス: `/api/admin/auth/me`
- 認証要否: 管理者必須
- 概要: Admin Me
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 401 Unauthorized

### `GET /api/admin/authors/{author_user_id}/payout_profile`

- HTTPメソッド: `GET`
- パス: `/api/admin/authors/{author_user_id}/payout_profile`
- 認証要否: 管理者必須
- 概要: Admin Author Payout Profile
- リクエスト例:
```json
{
  "author_user_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `DELETE /api/admin/board/posts/{post_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/admin/board/posts/{post_id}`
- 認証要否: 管理者必須
- 概要: Admin Delete Board Post
- リクエスト例:
```json
{
  "post_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/admin/contact/messages`

- HTTPメソッド: `GET`
- パス: `/api/admin/contact/messages`
- 認証要否: 管理者必須
- 概要: Admin List Contact Messages
- リクエスト例:
```json
{
  "limit": 50
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/admin/contact/messages`

- HTTPメソッド: `POST`
- パス: `/api/admin/contact/messages`
- 認証要否: 管理者必須
- 概要: Admin Create Contact Message
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/admin/email-test-all-users`

- HTTPメソッド: `POST`
- パス: `/api/admin/email-test-all-users`
- 認証要否: 管理者必須
- 概要: Admin Send Test Email All Users
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request

### `GET /api/admin/i18n/jobs`

- HTTPメソッド: `GET`
- パス: `/api/admin/i18n/jobs`
- 認証要否: 管理者必須
- 概要: Admin List I18N Jobs
- リクエスト例:
```json
{
  "limit": 20
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/admin/i18n/jobs/start`

- HTTPメソッド: `POST`
- パス: `/api/admin/i18n/jobs/start`
- 認証要否: 管理者必須
- 概要: Admin Start I18N Job
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/admin/i18n/jobs/{job_id}`

- HTTPメソッド: `GET`
- パス: `/api/admin/i18n/jobs/{job_id}`
- 認証要否: 管理者必須
- 概要: Admin I18N Job Status
- リクエスト例:
```json
{
  "job_id": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/admin/i18n/jobs/{job_id}/cancel`

- HTTPメソッド: `POST`
- パス: `/api/admin/i18n/jobs/{job_id}/cancel`
- 認証要否: 管理者必須
- 概要: Admin Cancel I18N Job
- リクエスト例:
```json
{
  "job_id": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/admin/i18n/retranslate_remaining`

- HTTPメソッド: `POST`
- パス: `/api/admin/i18n/retranslate_remaining`
- 認証要否: 管理者必須
- 概要: Admin Retranslate Remaining I18N
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `DELETE /api/admin/indexing/carryover`

- HTTPメソッド: `DELETE`
- パス: `/api/admin/indexing/carryover`
- 認証要否: 管理者必須
- 概要: Admin Indexing Carryover Clear
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `GET /api/admin/indexing/carryover`

- HTTPメソッド: `GET`
- パス: `/api/admin/indexing/carryover`
- 認証要否: 管理者必須
- 概要: Admin Indexing Carryover
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/admin/indexing/submit`

- HTTPメソッド: `POST`
- パス: `/api/admin/indexing/submit`
- 認証要否: 管理者必須
- 概要: Admin Indexing Submit
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/admin/indexing/urls`

- HTTPメソッド: `GET`
- パス: `/api/admin/indexing/urls`
- 認証要否: 管理者必須
- 概要: Admin Indexing Urls
- リクエスト例:
```json
{
  "limit": 1000,
  "inspect": false
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/admin/indexnow/submit`

- HTTPメソッド: `POST`
- パス: `/api/admin/indexnow/submit`
- 認証要否: 管理者必須
- 概要: Admin Indexnow Submit
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `GET /api/admin/payouts`

- HTTPメソッド: `GET`
- パス: `/api/admin/payouts`
- 認証要否: 管理者必須
- 概要: Admin List Payouts
- リクエスト例:
```json
{
  "status": "string",
  "limit": 50
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/admin/payouts/generate`

- HTTPメソッド: `POST`
- パス: `/api/admin/payouts/generate`
- 認証要否: 管理者必須
- 概要: Generate Payouts
- リクエスト例:
```json
{
  "period": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/admin/payouts/preview`

- HTTPメソッド: `GET`
- パス: `/api/admin/payouts/preview`
- 認証要否: 管理者必須
- 概要: Preview Payouts
- リクエスト例:
```json
{
  "period": "string"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `GET /api/admin/payouts/timeline`

- HTTPメソッド: `GET`
- パス: `/api/admin/payouts/timeline`
- 認証要否: 管理者必須
- 概要: Admin Payouts Timeline
- リクエスト例:
```json
{
  "days": 90
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `POST /api/admin/payouts/{payout_id}/mark_failed`

- HTTPメソッド: `POST`
- パス: `/api/admin/payouts/{payout_id}/mark_failed`
- 認証要否: 管理者必須
- 概要: Mark Payout Failed
- リクエスト例:
```json
{
  "params": {
    "payout_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `POST /api/admin/payouts/{payout_id}/mark_paid`

- HTTPメソッド: `POST`
- パス: `/api/admin/payouts/{payout_id}/mark_paid`
- 認証要否: 管理者必須
- 概要: Mark Payout Paid
- リクエスト例:
```json
{
  "params": {
    "payout_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/admin/seo-pages`

- HTTPメソッド: `GET`
- パス: `/api/admin/seo-pages`
- 認証要否: 管理者必須
- 概要: Admin List Seo Pages
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: なし / OpenAPI未記載

### `POST /api/admin/seo-pages`

- HTTPメソッド: `POST`
- パス: `/api/admin/seo-pages`
- 認証要否: 管理者必須
- 概要: Admin Create Seo Page
- リクエスト例:
```json
{
  "example_key": "value"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/admin/seo-pages/{page_id}`

- HTTPメソッド: `GET`
- パス: `/api/admin/seo-pages/{page_id}`
- 認証要否: 管理者必須
- 概要: Admin Get Seo Page
- リクエスト例:
```json
{
  "page_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `PUT /api/admin/seo-pages/{page_id}`

- HTTPメソッド: `PUT`
- パス: `/api/admin/seo-pages/{page_id}`
- 認証要否: 管理者必須
- 概要: Admin Update Seo Page
- リクエスト例:
```json
{
  "params": {
    "page_id": 1
  },
  "body": {
    "example_key": "value"
  }
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/admin/supports/timeline`

- HTTPメソッド: `GET`
- パス: `/api/admin/supports/timeline`
- 認証要否: 管理者必須
- 概要: Admin Supports Timeline
- リクエスト例:
```json
{
  "days": 30,
  "limit": 10,
  "by": "author"
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `POST /api/admin/translations/backfill`

- HTTPメソッド: `POST`
- パス: `/api/admin/translations/backfill`
- 認証要否: 管理者必須
- 概要: Admin Backfill Translations
- リクエスト例:
```json
{}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 400 Bad Request, 422 Validation Error

### `GET /api/admin/users`

- HTTPメソッド: `GET`
- パス: `/api/admin/users`
- 認証要否: 管理者必須
- 概要: Admin List Users
- リクエスト例:
```json
{
  "limit": 50,
  "offset": 0
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error

### `DELETE /api/admin/users/{user_id}`

- HTTPメソッド: `DELETE`
- パス: `/api/admin/users/{user_id}`
- 認証要否: 管理者必須
- 概要: Admin Delete User
- リクエスト例:
```json
{
  "user_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 404 Not Found, 422 Validation Error

### `GET /api/admin/users/{user_id}/novels`

- HTTPメソッド: `GET`
- パス: `/api/admin/users/{user_id}/novels`
- 認証要否: 管理者必須
- 概要: Admin List User Novels
- リクエスト例:
```json
{
  "user_id": 1
}
```
- レスポンス例:
```json
"value"
```
- 主なエラー: 422 Validation Error
