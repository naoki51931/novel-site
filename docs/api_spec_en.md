# API Specification

- Generated from: FastAPI OpenAPI schema (`app.openapi()`)
- OpenAPI URL: `/api/openapi.json`
- Supplemented from: `backend/app/main.py`, `backend/app/routers/`, `backend/app/features/*_routes.py`, and related service source
- Note: authentication requirements and common errors that cannot be inferred from OpenAPI alone are supplemented from route and service implementations

## Authentication / OAuth

### `POST /api/auth/login`

- HTTP Method: `POST`
- Path: `/api/auth/login`
- Authentication: Not required
- Summary: Login
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 401 Unauthorized, 422 Validation Error

### `POST /api/auth/login-with-email-code`

- HTTP Method: `POST`
- Path: `/api/auth/login-with-email-code`
- Authentication: Not required
- Summary: Login With Email Code
- Request Example:
```json
{
  "email": "user@example.com",
  "code": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/auth/login/start`

- HTTP Method: `POST`
- Path: `/api/auth/login/start`
- Authentication: Not required
- Summary: Login Start
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 401 Unauthorized, 422 Validation Error

### `POST /api/auth/login/verify`

- HTTP Method: `POST`
- Path: `/api/auth/login/verify`
- Authentication: Not required
- Summary: Login Verify
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/auth/oauth/{provider}/callback`

- HTTP Method: `GET`
- Path: `/api/auth/oauth/{provider}/callback`
- Authentication: Not required
- Summary: Oauth Callback
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `GET /api/auth/oauth/{provider}/start`

- HTTP Method: `GET`
- Path: `/api/auth/oauth/{provider}/start`
- Authentication: Not required
- Summary: Oauth Start
- Request Example:
```json
{
  "provider": "string",
  "redirect": "string",
  "client": "string",
  "direct": 0
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `POST /api/auth/password-reset/confirm`

- HTTP Method: `POST`
- Path: `/api/auth/password-reset/confirm`
- Authentication: Not required
- Summary: Password Reset Confirm
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/auth/password-reset/request`

- HTTP Method: `POST`
- Path: `/api/auth/password-reset/request`
- Authentication: Not required
- Summary: Password Reset Request
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/auth/register`

- HTTP Method: `POST`
- Path: `/api/auth/register`
- Authentication: Not required
- Summary: Register User
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/auth/register/email/start`

- HTTP Method: `POST`
- Path: `/api/auth/register/email/start`
- Authentication: Not required
- Summary: Start Register Email Verification
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `POST /api/auth/request-email-code`

- HTTP Method: `POST`
- Path: `/api/auth/request-email-code`
- Authentication: Not required
- Summary: Request Email Code
- Request Example:
```json
{
  "email": "user@example.com"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/mobile-push/register`

- HTTP Method: `POST`
- Path: `/api/mobile-push/register`
- Authentication: 必須
- Summary: Register Mobile Push Token
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/mobile-push/unregister`

- HTTP Method: `POST`
- Path: `/api/mobile-push/unregister`
- Authentication: 必須
- Summary: Unregister Mobile Push Token
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/push/debug`

- HTTP Method: `POST`
- Path: `/api/push/debug`
- Authentication: 必須
- Summary: Push Debug Log
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/push/public_key`

- HTTP Method: `GET`
- Path: `/api/push/public_key`
- Authentication: Not required
- Summary: Get Push Public Key
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/push/subscribe`

- HTTP Method: `POST`
- Path: `/api/push/subscribe`
- Authentication: 必須
- Summary: Subscribe Push Notifications
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/push/unsubscribe`

- HTTP Method: `POST`
- Path: `/api/push/unsubscribe`
- Authentication: 必須
- Summary: Unsubscribe Push Notifications
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

## Public Novels / Authors / Search

### `GET /api/authors/{author_id}`

- HTTP Method: `GET`
- Path: `/api/authors/{author_id}`
- Authentication: Not required
- Summary: Read Public Author
- Request Example:
```json
{
  "author_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/authors/{author_id}/favorite-tags`

- HTTP Method: `GET`
- Path: `/api/authors/{author_id}/favorite-tags`
- Authentication: 必須
- Summary: Get Author Favorite Tags
- Request Example:
```json
{
  "author_id": 1,
  "limit": 12
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/authors/{author_id}/novels`

- HTTP Method: `GET`
- Path: `/api/authors/{author_id}/novels`
- Authentication: Not required
- Summary: List Public Author Novels
- Request Example:
```json
{
  "author_id": 1,
  "sort": "latest"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/authors/{author_id}/stats`

- HTTP Method: `GET`
- Path: `/api/authors/{author_id}/stats`
- Authentication: 必須
- Summary: Get Author Stats
- Request Example:
```json
{
  "author_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/contact/messages`

- HTTP Method: `POST`
- Path: `/api/contact/messages`
- Authentication: 任意
- Summary: Public Create Contact Message
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/me`

- HTTP Method: `GET`
- Path: `/api/me`
- Authentication: 必須
- Summary: Read Me
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/me/ai/chat/favorites`

- HTTP Method: `GET`
- Path: `/api/me/ai/chat/favorites`
- Authentication: 必須
- Summary: List My Ai Chat Favorites
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/me/ai/chat/usage-history`

- HTTP Method: `GET`
- Path: `/api/me/ai/chat/usage-history`
- Authentication: 必須
- Summary: List My Ai Chat Usage History
- Request Example:
```json
{
  "limit": 50
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/me/analytics/novels`

- HTTP Method: `GET`
- Path: `/api/me/analytics/novels`
- Authentication: 必須
- Summary: List My Novel Analytics
- Request Example:
```json
{
  "month": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/me/analytics/novels/{novel_id}`

- HTTP Method: `GET`
- Path: `/api/me/analytics/novels/{novel_id}`
- Authentication: 必須
- Summary: Read My Novel Analytics
- Request Example:
```json
{
  "novel_id": 1,
  "month": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/me/favorites`

- HTTP Method: `GET`
- Path: `/api/me/favorites`
- Authentication: 必須
- Summary: List My Favorites
- Request Example:
```json
{
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/me/scheduled-episodes`

- HTTP Method: `GET`
- Path: `/api/me/scheduled-episodes`
- Authentication: 必須
- Summary: List My Scheduled Episodes
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/me/tag-follows`

- HTTP Method: `GET`
- Path: `/api/me/tag-follows`
- Authentication: 必須
- Summary: List My Tag Follows
- Request Example:
```json
{
  "limit": 100
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/me/view-history/ai-public-chats`

- HTTP Method: `GET`
- Path: `/api/me/view-history/ai-public-chats`
- Authentication: 必須
- Summary: List My Public Ai Chat View History
- Request Example:
```json
{
  "limit": 50
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/me/view-history/novels`

- HTTP Method: `GET`
- Path: `/api/me/view-history/novels`
- Authentication: 必須
- Summary: List My Novel View History
- Request Example:
```json
{
  "limit": 50,
  "offset": 0
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/me/view-history/record`

- HTTP Method: `POST`
- Path: `/api/me/view-history/record`
- Authentication: 必須
- Summary: Record My View History
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/notifications`

- HTTP Method: `GET`
- Path: `/api/notifications`
- Authentication: 必須
- Summary: List Notifications
- Request Example:
```json
{
  "limit": 50,
  "offset": 0,
  "unread_only": false,
  "group": "all",
  "notif_type": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/notifications/counts`

- HTTP Method: `GET`
- Path: `/api/notifications/counts`
- Authentication: 必須
- Summary: Notification Counts
- Request Example:
```json
{
  "unread_only": false
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/notifications/read_all`

- HTTP Method: `POST`
- Path: `/api/notifications/read_all`
- Authentication: 必須
- Summary: Mark All Notifications Read
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/notifications/unread_count`

- HTTP Method: `GET`
- Path: `/api/notifications/unread_count`
- Authentication: 必須
- Summary: Unread Notification Count
- Request Example:
```json
{
  "group": "all"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/notifications/{notification_id}`

- HTTP Method: `DELETE`
- Path: `/api/notifications/{notification_id}`
- Authentication: 必須
- Summary: Delete Notification
- Request Example:
```json
{
  "notification_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/notifications/{notification_id}/read`

- HTTP Method: `POST`
- Path: `/api/notifications/{notification_id}/read`
- Authentication: 必須
- Summary: Mark Notification Read
- Request Example:
```json
{
  "notification_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/public/novels`

- HTTP Method: `GET`
- Path: `/api/public/novels`
- Authentication: 必須
- Summary: List Public Novels
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/public/users/{username}`

- HTTP Method: `GET`
- Path: `/api/public/users/{username}`
- Authentication: Not required
- Summary: Read Public User
- Request Example:
```json
{
  "username": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/public/users/{username}/favorites`

- HTTP Method: `GET`
- Path: `/api/public/users/{username}/favorites`
- Authentication: 必須
- Summary: List Public User Favorites
- Request Example:
```json
{
  "username": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/public/users/{username}/novels`

- HTTP Method: `GET`
- Path: `/api/public/users/{username}/novels`
- Authentication: 必須
- Summary: List Public User Novels
- Request Example:
```json
{
  "username": "string",
  "sort": "latest"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/search/tags`

- HTTP Method: `GET`
- Path: `/api/search/tags`
- Authentication: Not required
- Summary: Search Public Tags
- Request Example:
```json
{
  "q": "string",
  "limit": 8
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/search/users`

- HTTP Method: `GET`
- Path: `/api/search/users`
- Authentication: Not required
- Summary: Search Public Users
- Request Example:
```json
{
  "q": "string",
  "limit": 8
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/seo-pages/{slug}`

- HTTP Method: `GET`
- Path: `/api/seo-pages/{slug}`
- Authentication: Not required
- Summary: Read Public Seo Page
- Request Example:
```json
{
  "slug": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/users/me`

- HTTP Method: `GET`
- Path: `/api/users/me`
- Authentication: 必須
- Summary: Read Profile
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: 401 Unauthorized

### `PUT /api/users/me`

- HTTP Method: `PUT`
- Path: `/api/users/me`
- Authentication: 必須
- Summary: Update Profile
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `DELETE /api/users/{user_id}/follow`

- HTTP Method: `DELETE`
- Path: `/api/users/{user_id}/follow`
- Authentication: 必須
- Summary: Unfollow User
- Request Example:
```json
{
  "user_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/users/{user_id}/follow`

- HTTP Method: `POST`
- Path: `/api/users/{user_id}/follow`
- Authentication: 必須
- Summary: Follow User
- Request Example:
```json
{
  "user_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/users/{user_id}/follow-status`

- HTTP Method: `GET`
- Path: `/api/users/{user_id}/follow-status`
- Authentication: 必須
- Summary: Get Follow Status
- Request Example:
```json
{
  "user_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/users/{user_id}/followers`

- HTTP Method: `GET`
- Path: `/api/users/{user_id}/followers`
- Authentication: 必須
- Summary: List Followers
- Request Example:
```json
{
  "user_id": 1,
  "limit": 50,
  "offset": 0
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/users/{user_id}/following`

- HTTP Method: `GET`
- Path: `/api/users/{user_id}/following`
- Authentication: 必須
- Summary: List Following
- Request Example:
```json
{
  "user_id": 1,
  "limit": 50,
  "offset": 0
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /ogp/novel/{novel_id}.png`

- HTTP Method: `GET`
- Path: `/ogp/novel/{novel_id}.png`
- Authentication: Not required
- Summary: Novel Og Image
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /prerender/episodes/{episode_id}`

- HTTP Method: `GET`
- Path: `/prerender/episodes/{episode_id}`
- Authentication: Not required
- Summary: Prerender Episode Page
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /prerender/novels/{novel_id}`

- HTTP Method: `GET`
- Path: `/prerender/novels/{novel_id}`
- Authentication: Not required
- Summary: Prerender Novel Page
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /robots.txt`

- HTTP Method: `GET`
- Path: `/robots.txt`
- Authentication: Not required
- Summary: Robots Txt
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /share/episodes/{episode_id}`

- HTTP Method: `GET`
- Path: `/share/episodes/{episode_id}`
- Authentication: Not required
- Summary: Share Episode Page
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /share/episodes/{episode_id}/og-image.png`

- HTTP Method: `GET`
- Path: `/share/episodes/{episode_id}/og-image.png`
- Authentication: Not required
- Summary: Share Episode Og Image
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `GET /sitemap-authors.xml`

- HTTP Method: `GET`
- Path: `/sitemap-authors.xml`
- Authentication: Not required
- Summary: Sitemap Authors Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap-episodes.xml`

- HTTP Method: `GET`
- Path: `/sitemap-episodes.xml`
- Authentication: Not required
- Summary: Sitemap Episodes Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap-index.xml`

- HTTP Method: `GET`
- Path: `/sitemap-index.xml`
- Authentication: Not required
- Summary: Sitemap Index Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap-main.xml`

- HTTP Method: `GET`
- Path: `/sitemap-main.xml`
- Authentication: Not required
- Summary: Sitemap Main Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap-novels.xml`

- HTTP Method: `GET`
- Path: `/sitemap-novels.xml`
- Authentication: Not required
- Summary: Sitemap Novels Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap-seo-pages.xml`

- HTTP Method: `GET`
- Path: `/sitemap-seo-pages.xml`
- Authentication: Not required
- Summary: Sitemap Seo Pages Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap-static.xml`

- HTTP Method: `GET`
- Path: `/sitemap-static.xml`
- Authentication: Not required
- Summary: Sitemap Static Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap-tags.xml`

- HTTP Method: `GET`
- Path: `/sitemap-tags.xml`
- Authentication: Not required
- Summary: Sitemap Tags Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /sitemap.xml`

- HTTP Method: `GET`
- Path: `/sitemap.xml`
- Authentication: Not required
- Summary: Sitemap Xml
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /{indexnow_key_file}.txt`

- HTTP Method: `GET`
- Path: `/{indexnow_key_file}.txt`
- Authentication: Not required
- Summary: Indexnow Key File
- Request Example:
```json
{
  "indexnow_key_file": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

## Novels / Episodes / Tags / Series

### `GET /api/author/dashboard`

- HTTP Method: `GET`
- Path: `/api/author/dashboard`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Get Author Dashboard
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/author/dashboard/novels/{novel_id}/daily`

- HTTP Method: `GET`
- Path: `/api/author/dashboard/novels/{novel_id}/daily`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Get Author Novel Daily Metrics
- Request Example:
```json
{
  "novel_id": 1,
  "days": 30
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/author/dashboard/top-novels`

- HTTP Method: `GET`
- Path: `/api/author/dashboard/top-novels`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Get Author Top Novels
- Request Example:
```json
{
  "limit": 10,
  "sort": "views"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/covers/generate`

- HTTP Method: `POST`
- Path: `/api/covers/generate`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Generate Cover
- Request Example:
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
- Response Example:
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
- Common Errors: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `GET /api/covers/history`

- HTTP Method: `GET`
- Path: `/api/covers/history`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Get Cover History
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
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
- Common Errors: 422 Validation Error

### `DELETE /api/covers/history/{cover_id}`

- HTTP Method: `DELETE`
- Path: `/api/covers/history/{cover_id}`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Delete Cover History Item
- Request Example:
```json
{
  "cover_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `DELETE /api/episodes/{episode_id}`

- HTTP Method: `DELETE`
- Path: `/api/episodes/{episode_id}`
- Authentication: 必須
- Summary: Delete Episode
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/episodes/{episode_id}`

- HTTP Method: `GET`
- Path: `/api/episodes/{episode_id}`
- Authentication: Not required
- Summary: Get Episode
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `PUT /api/episodes/{episode_id}`

- HTTP Method: `PUT`
- Path: `/api/episodes/{episode_id}`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Update Episode
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/cover-image`

- HTTP Method: `DELETE`
- Path: `/api/episodes/{episode_id}/cover-image`
- Authentication: 必須
- Summary: Delete Episode Cover Image
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 422 Validation Error

### `POST /api/episodes/{episode_id}/cover-image`

- HTTP Method: `POST`
- Path: `/api/episodes/{episode_id}/cover-image`
- Authentication: 必須
- Summary: Upload Episode Cover Image
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `GET /api/episodes/{episode_id}/edit`

- HTTP Method: `GET`
- Path: `/api/episodes/{episode_id}/edit`
- Authentication: 必須
- Summary: Get Episode For Edit
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/illusts`

- HTTP Method: `POST`
- Path: `/api/episodes/{episode_id}/illusts`
- Authentication: 必須
- Summary: Upload Episode Illust
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/illusts/{illust_id}`

- HTTP Method: `DELETE`
- Path: `/api/episodes/{episode_id}/illusts/{illust_id}`
- Authentication: 必須
- Summary: Delete Episode Illust
- Request Example:
```json
{
  "episode_id": 1,
  "illust_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/like`

- HTTP Method: `DELETE`
- Path: `/api/episodes/{episode_id}/like`
- Authentication: 必須
- Summary: Unlike Episode
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/like`

- HTTP Method: `POST`
- Path: `/api/episodes/{episode_id}/like`
- Authentication: 必須
- Summary: Like Episode
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/title_candidates`

- HTTP Method: `POST`
- Path: `/api/episodes/{episode_id}/title_candidates`
- Authentication: 必須
- Summary: Generate Episode Title Candidates
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/episodes/{episode_id}/translations/{lang}`

- HTTP Method: `GET`
- Path: `/api/episodes/{episode_id}/translations/{lang}`
- Authentication: Not required
- Summary: Get Episode Translation
- Request Example:
```json
{
  "episode_id": 1,
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/episodes/{episode_id}/unschedule`

- HTTP Method: `POST`
- Path: `/api/episodes/{episode_id}/unschedule`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Unschedule Episode
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 422 Validation Error

### `GET /api/novels`

- HTTP Method: `GET`
- Path: `/api/novels`
- Authentication: 必須
- Summary: List Novels
- Request Example:
```json
{
  "mine": false,
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/novels`

- HTTP Method: `POST`
- Path: `/api/novels`
- Authentication: 必須
- Summary: Create Novel
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/novels/`

- HTTP Method: `POST`
- Path: `/api/novels/`
- Authentication: 必須
- Summary: Create Novel
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/novels/{novel_id}`

- HTTP Method: `DELETE`
- Path: `/api/novels/{novel_id}`
- Authentication: 必須
- Summary: Delete Novel
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/novels/{novel_id}`

- HTTP Method: `GET`
- Path: `/api/novels/{novel_id}`
- Authentication: Not required
- Summary: Get Novel Detail
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `PUT /api/novels/{novel_id}`

- HTTP Method: `PUT`
- Path: `/api/novels/{novel_id}`
- Authentication: 必須
- Summary: Update Novel
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/novels/{novel_id}/cover`

- HTTP Method: `DELETE`
- Path: `/api/novels/{novel_id}/cover`
- Authentication: 必須
- Summary: Delete Novel Cover
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/novels/{novel_id}/cover`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/cover`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Set Novel Cover
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `POST /api/novels/{novel_id}/cover-image`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/cover-image`
- Authentication: 必須
- Summary: Upload Novel Cover Image
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/novels/{novel_id}/episodes`

- HTTP Method: `GET`
- Path: `/api/novels/{novel_id}/episodes`
- Authentication: Not required
- Summary: List Episodes
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/novels/{novel_id}/episodes`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/episodes`
- Authentication: 必須 (一部プレミアム条件あり)
- Summary: Create Episode
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `DELETE /api/novels/{novel_id}/favorite`

- HTTP Method: `DELETE`
- Path: `/api/novels/{novel_id}/favorite`
- Authentication: 必須
- Summary: Unfavorite Novel
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/novels/{novel_id}/favorite`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/favorite`
- Authentication: 必須
- Summary: Favorite Novel
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/novels/{novel_id}/like`

- HTTP Method: `DELETE`
- Path: `/api/novels/{novel_id}/like`
- Authentication: 必須
- Summary: Unlike Novel
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/novels/{novel_id}/like`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/like`
- Authentication: 必須
- Summary: Like Novel
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/novels/{novel_id}/summary_candidates`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/summary_candidates`
- Authentication: 必須
- Summary: Generate Novel Summary Candidates
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `POST /api/novels/{novel_id}/tag_candidates`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/tag_candidates`
- Authentication: 必須
- Summary: Generate Novel Tag Candidates
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `POST /api/novels/{novel_id}/title_candidates`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/title_candidates`
- Authentication: 必須
- Summary: Generate Novel Title Candidates
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/novels/{novel_id}/translations/{lang}`

- HTTP Method: `GET`
- Path: `/api/novels/{novel_id}/translations/{lang}`
- Authentication: Not required
- Summary: Get Novel Translation
- Request Example:
```json
{
  "novel_id": 1,
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/series`

- HTTP Method: `GET`
- Path: `/api/series`
- Authentication: Not required
- Summary: List Series Overview
- Request Example:
```json
{
  "q": "string",
  "limit": 30
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/series/{series_name}/novels`

- HTTP Method: `GET`
- Path: `/api/series/{series_name}/novels`
- Authentication: Not required
- Summary: List Series Novels
- Request Example:
```json
{
  "series_name": "string",
  "limit": 60
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/tags`

- HTTP Method: `GET`
- Path: `/api/tags`
- Authentication: Not required
- Summary: List Tags
- Request Example:
```json
{
  "limit": 100
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/tags/{tag_name}`

- HTTP Method: `GET`
- Path: `/api/tags/{tag_name}`
- Authentication: Not required
- Summary: Read Tag Detail
- Request Example:
```json
{
  "tag_name": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `DELETE /api/tags/{tag_name}/follow`

- HTTP Method: `DELETE`
- Path: `/api/tags/{tag_name}/follow`
- Authentication: 必須
- Summary: Unfollow Tag
- Request Example:
```json
{
  "tag_name": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/tags/{tag_name}/follow`

- HTTP Method: `POST`
- Path: `/api/tags/{tag_name}/follow`
- Authentication: 必須
- Summary: Follow Tag
- Request Example:
```json
{
  "tag_name": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/tags/{tag_name}/follow-status`

- HTTP Method: `GET`
- Path: `/api/tags/{tag_name}/follow-status`
- Authentication: 必須
- Summary: Read Tag Follow Status
- Request Example:
```json
{
  "tag_name": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/tags/{tag_name}/novels`

- HTTP Method: `GET`
- Path: `/api/tags/{tag_name}/novels`
- Authentication: Not required
- Summary: List Tag Novels
- Request Example:
```json
{
  "tag_name": "string",
  "sort": "popular",
  "limit": 60,
  "offset": 0
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/tags/{tag_name}/related`

- HTTP Method: `GET`
- Path: `/api/tags/{tag_name}/related`
- Authentication: Not required
- Summary: List Related Tags
- Request Example:
```json
{
  "tag_name": "string",
  "limit": 12
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

## Feed / Recommendations

### `GET /api/feed/following`

- HTTP Method: `GET`
- Path: `/api/feed/following`
- Authentication: 必須
- Summary: List Following Feed
- Request Example:
```json
{
  "limit": 20
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/feed/following-tags`

- HTTP Method: `GET`
- Path: `/api/feed/following-tags`
- Authentication: 必須
- Summary: List Following Tags Feed
- Request Example:
```json
{
  "limit": 20
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/feed/history`

- HTTP Method: `GET`
- Path: `/api/feed/history`
- Authentication: 必須
- Summary: List History Feed
- Request Example:
```json
{
  "limit": 12
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/feed/new`

- HTTP Method: `GET`
- Path: `/api/feed/new`
- Authentication: 任意
- Summary: List New Feed
- Request Example:
```json
{
  "limit": 20,
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/feed/pickups`

- HTTP Method: `GET`
- Path: `/api/feed/pickups`
- Authentication: 必須
- Summary: List Pickups Feed
- Request Example:
```json
{
  "limit": 8
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/feed/recommended`

- HTTP Method: `GET`
- Path: `/api/feed/recommended`
- Authentication: 任意
- Summary: List Recommended Feed
- Request Example:
```json
{
  "limit": 12,
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/feed/trending`

- HTTP Method: `GET`
- Path: `/api/feed/trending`
- Authentication: 任意
- Summary: List Trending Feed
- Request Example:
```json
{
  "limit": 20,
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/public/novels/ranking`

- HTTP Method: `GET`
- Path: `/api/public/novels/ranking`
- Authentication: 必須
- Summary: List Public Novel Rankings
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 403 Forbidden, 422 Validation Error

### `GET /api/public/novels/recommended`

- HTTP Method: `GET`
- Path: `/api/public/novels/recommended`
- Authentication: 任意
- Summary: List Recommended Public Novels
- Request Example:
```json
{
  "limit": 12,
  "lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/trending-tags`

- HTTP Method: `GET`
- Path: `/api/trending-tags`
- Authentication: Not required
- Summary: List Trending Tags
- Request Example:
```json
{
  "days": 7,
  "limit": 20
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

## Comments / DM / Board

### `GET /api/board/posts`

- HTTP Method: `GET`
- Path: `/api/board/posts`
- Authentication: Not required
- Summary: List Board Posts
- Request Example:
```json
{
  "limit": 1000
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/board/posts`

- HTTP Method: `POST`
- Path: `/api/board/posts`
- Authentication: 任意
- Summary: Create Board Post
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `POST /api/dms`

- HTTP Method: `POST`
- Path: `/api/dms`
- Authentication: 必須
- Summary: Create Dm Thread
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/dms/{thread_id}`

- HTTP Method: `GET`
- Path: `/api/dms/{thread_id}`
- Authentication: 必須
- Summary: Read Dm Thread
- Request Example:
```json
{
  "thread_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `POST /api/dms/{thread_id}/messages`

- HTTP Method: `POST`
- Path: `/api/dms/{thread_id}/messages`
- Authentication: 必須
- Summary: Create Dm Message
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/episodes/{episode_id}/comments`

- HTTP Method: `GET`
- Path: `/api/episodes/{episode_id}/comments`
- Authentication: Not required
- Summary: Get Episode Comments
- Request Example:
```json
{
  "episode_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/episodes/{episode_id}/comments`

- HTTP Method: `POST`
- Path: `/api/episodes/{episode_id}/comments`
- Authentication: 必須
- Summary: Post Episode Comment
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `DELETE /api/episodes/{episode_id}/comments/{comment_id}`

- HTTP Method: `DELETE`
- Path: `/api/episodes/{episode_id}/comments/{comment_id}`
- Authentication: 必須
- Summary: Delete Episode Comment
- Request Example:
```json
{
  "episode_id": 1,
  "comment_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

### `GET /api/novels/{novel_id}/comments`

- HTTP Method: `GET`
- Path: `/api/novels/{novel_id}/comments`
- Authentication: Not required
- Summary: Get Comments
- Request Example:
```json
{
  "novel_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/novels/{novel_id}/comments`

- HTTP Method: `POST`
- Path: `/api/novels/{novel_id}/comments`
- Authentication: 必須
- Summary: Post Comment
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `DELETE /api/novels/{novel_id}/comments/{comment_id}`

- HTTP Method: `DELETE`
- Path: `/api/novels/{novel_id}/comments/{comment_id}`
- Authentication: 必須
- Summary: Delete Comment
- Request Example:
```json
{
  "novel_id": 1,
  "comment_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 403 Forbidden, 404 Not Found, 422 Validation Error

## Support / Stripe / Membership / Payout

### `GET /api/authors/me/balance`

- HTTP Method: `GET`
- Path: `/api/authors/me/balance`
- Authentication: 必須
- Summary: Get Author Balance
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/authors/me/payout_profile`

- HTTP Method: `POST`
- Path: `/api/authors/me/payout_profile`
- Authentication: 必須
- Summary: Update Payout Profile
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/authors/me/support_plans`

- HTTP Method: `GET`
- Path: `/api/authors/me/support_plans`
- Authentication: 必須
- Summary: List My Support Plans
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/authors/me/support_plans`

- HTTP Method: `POST`
- Path: `/api/authors/me/support_plans`
- Authentication: 必須
- Summary: Create Support Plan
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 409 Conflict, 422 Validation Error

### `PATCH /api/authors/me/support_plans/{plan_id}`

- HTTP Method: `PATCH`
- Path: `/api/authors/me/support_plans/{plan_id}`
- Authentication: 必須
- Summary: Update Support Plan
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 409 Conflict, 422 Validation Error

### `POST /api/authors/me/support_plans/{plan_id}/activate`

- HTTP Method: `POST`
- Path: `/api/authors/me/support_plans/{plan_id}/activate`
- Authentication: 必須
- Summary: Activate Support Plan
- Request Example:
```json
{
  "plan_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 409 Conflict, 422 Validation Error

### `POST /api/authors/me/support_plans/{plan_id}/deactivate`

- HTTP Method: `POST`
- Path: `/api/authors/me/support_plans/{plan_id}/deactivate`
- Authentication: 必須
- Summary: Deactivate Support Plan
- Request Example:
```json
{
  "plan_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/memberships/checkout`

- HTTP Method: `POST`
- Path: `/api/memberships/checkout`
- Authentication: 必須
- Summary: Memberships Checkout
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

### `POST /api/stripe/create-checkout-session`

- HTTP Method: `POST`
- Path: `/api/stripe/create-checkout-session`
- Authentication: 必須
- Summary: Stripe Checkout
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: 500 Internal Server Error

### `POST /api/stripe/webhook`

- HTTP Method: `POST`
- Path: `/api/stripe/webhook`
- Authentication: Not required (Stripe署名必須)
- Summary: Stripe Webhook
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `GET /api/support_plans`

- HTTP Method: `GET`
- Path: `/api/support_plans`
- Authentication: Not required
- Summary: List Support Plans
- Request Example:
```json
{
  "author_user_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/supports/checkout`

- HTTP Method: `POST`
- Path: `/api/supports/checkout`
- Authentication: 任意
- Summary: Supports Checkout
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error, 500 Internal Server Error

## AI Novels / AI Chat / Translation

### `POST /api/ai/character_terms`

- HTTP Method: `POST`
- Path: `/api/ai/character_terms`
- Authentication: Not required
- Summary: Extract Ai Character Terms
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat`

- HTTP Method: `POST`
- Path: `/api/ai/chat`
- Authentication: Not required
- Summary: Ai Chat
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/chat/access`

- HTTP Method: `GET`
- Path: `/api/ai/chat/access`
- Authentication: Not required
- Summary: Get Ai Chat Access Status
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/chat/addon/checkout`

- HTTP Method: `POST`
- Path: `/api/ai/chat/addon/checkout`
- Authentication: 必須
- Summary: Create Ai Chat Addon Checkout
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 402 Payment Required, 422 Validation Error, 500 Internal Server Error

### `POST /api/ai/chat/auto_continue`

- HTTP Method: `POST`
- Path: `/api/ai/chat/auto_continue`
- Authentication: Not required
- Summary: Ai Chat Auto Continue
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/character/anime_title_candidates`

- HTTP Method: `POST`
- Path: `/api/ai/chat/character/anime_title_candidates`
- Authentication: Not required
- Summary: Ai Chat Character Anime Title Candidates
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/character/augment`

- HTTP Method: `POST`
- Path: `/api/ai/chat/character/augment`
- Authentication: Not required
- Summary: Augment Ai Chat Character
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/chat/characters`

- HTTP Method: `GET`
- Path: `/api/ai/chat/characters`
- Authentication: Not required
- Summary: List Ai Chat Characters
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/chat/characters`

- HTTP Method: `POST`
- Path: `/api/ai/chat/characters`
- Authentication: Not required
- Summary: Create Ai Chat Character
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/ai/chat/characters/{character_id}`

- HTTP Method: `DELETE`
- Path: `/api/ai/chat/characters/{character_id}`
- Authentication: Not required
- Summary: Delete Ai Chat Character
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `PUT /api/ai/chat/characters/{character_id}`

- HTTP Method: `PUT`
- Path: `/api/ai/chat/characters/{character_id}`
- Authentication: Not required
- Summary: Update Ai Chat Character
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/chat/characters/{character_id}/engagement_summary`

- HTTP Method: `GET`
- Path: `/api/ai/chat/characters/{character_id}/engagement_summary`
- Authentication: Not required
- Summary: Get Ai Chat Engagement Summary
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/characters/{character_id}/image`

- HTTP Method: `POST`
- Path: `/api/ai/chat/characters/{character_id}/image`
- Authentication: Not required
- Summary: Upload Ai Chat Character Image
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/chat/characters/{character_id}/latest_prompt_preview`

- HTTP Method: `GET`
- Path: `/api/ai/chat/characters/{character_id}/latest_prompt_preview`
- Authentication: Not required
- Summary: Get Ai Chat Latest Prompt Preview
- Request Example:
```json
{
  "character_id": 1,
  "r18": false
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/chat/characters/{character_id}/messages`

- HTTP Method: `GET`
- Path: `/api/ai/chat/characters/{character_id}/messages`
- Authentication: Not required
- Summary: List Ai Chat Messages
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/characters/{character_id}/messages/images`

- HTTP Method: `POST`
- Path: `/api/ai/chat/characters/{character_id}/messages/images`
- Authentication: Not required
- Summary: Upload Ai Chat Message Images
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/characters/{character_id}/messages/import`

- HTTP Method: `POST`
- Path: `/api/ai/chat/characters/{character_id}/messages/import`
- Authentication: Not required
- Summary: Import Ai Chat Messages
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/ai/chat/characters/{character_id}/messages/{message_id}`

- HTTP Method: `DELETE`
- Path: `/api/ai/chat/characters/{character_id}/messages/{message_id}`
- Authentication: Not required
- Summary: Delete Ai Chat Messages From Point
- Request Example:
```json
{
  "character_id": 1,
  "message_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/ai/chat/characters/{character_id}/messages/{message_id}/images/{image_index}`

- HTTP Method: `DELETE`
- Path: `/api/ai/chat/characters/{character_id}/messages/{message_id}/images/{image_index}`
- Authentication: Not required
- Summary: Delete Ai Chat Message Image
- Request Example:
```json
{
  "character_id": 1,
  "message_id": 1,
  "image_index": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `PATCH /api/ai/chat/characters/{character_id}/publish`

- HTTP Method: `PATCH`
- Path: `/api/ai/chat/characters/{character_id}/publish`
- Authentication: Not required
- Summary: Publish Ai Chat Character
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/generate_image`

- HTTP Method: `POST`
- Path: `/api/ai/chat/generate_image`
- Authentication: Not required
- Summary: Ai Chat Generate Image
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/next_user_lines`

- HTTP Method: `POST`
- Path: `/api/ai/chat/next_user_lines`
- Authentication: Not required
- Summary: Ai Chat Next User Lines
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/chat/public/characters`

- HTTP Method: `GET`
- Path: `/api/ai/chat/public/characters`
- Authentication: Not required
- Summary: List Public Ai Chat Characters
- Request Example:
```json
{
  "q": "",
  "limit": 20,
  "offset": 0
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/chat/public/characters/{character_id}`

- HTTP Method: `GET`
- Path: `/api/ai/chat/public/characters/{character_id}`
- Authentication: Not required
- Summary: Get Public Ai Chat Character Detail
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
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
- Common Errors: 422 Validation Error

### `DELETE /api/ai/chat/public/characters/{character_id}/favorite`

- HTTP Method: `DELETE`
- Path: `/api/ai/chat/public/characters/{character_id}/favorite`
- Authentication: 必須
- Summary: Unfavorite Public Ai Chat Character
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/public/characters/{character_id}/favorite`

- HTTP Method: `POST`
- Path: `/api/ai/chat/public/characters/{character_id}/favorite`
- Authentication: 必須
- Summary: Favorite Public Ai Chat Character
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/ai/chat/public/characters/{character_id}/like`

- HTTP Method: `DELETE`
- Path: `/api/ai/chat/public/characters/{character_id}/like`
- Authentication: 必須
- Summary: Unlike Public Ai Chat Character
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/chat/public/characters/{character_id}/like`

- HTTP Method: `POST`
- Path: `/api/ai/chat/public/characters/{character_id}/like`
- Authentication: 必須
- Summary: Like Public Ai Chat Character
- Request Example:
```json
{
  "character_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/episodes/assist_candidates`

- HTTP Method: `POST`
- Path: `/api/ai/episodes/assist_candidates`
- Authentication: Not required
- Summary: Generate Episode Assist Candidates
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/episodes/{episode_id}/continue`

- HTTP Method: `POST`
- Path: `/api/ai/episodes/{episode_id}/continue`
- Authentication: Not required
- Summary: Generate Ai Episode Continue
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/episodes/{episode_id}/continue_job`

- HTTP Method: `POST`
- Path: `/api/ai/episodes/{episode_id}/continue_job`
- Authentication: Not required
- Summary: Create Ai Episode Continue Job
- Request Example:
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
- Response Example:
```json
{
  "job_id": 1,
  "status": "string"
}
```
- Common Errors: 422 Validation Error

### `GET /api/ai/jobs`

- HTTP Method: `GET`
- Path: `/api/ai/jobs`
- Authentication: Admin required
- Summary: List All Ai Jobs
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/jobs/kill_all`

- HTTP Method: `POST`
- Path: `/api/ai/jobs/kill_all`
- Authentication: Admin required
- Summary: Kill All Ai Jobs
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/jobs/kill_me`

- HTTP Method: `POST`
- Path: `/api/ai/jobs/kill_me`
- Authentication: 必須
- Summary: Kill My Ai Jobs
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/jobs/kill_selected`

- HTTP Method: `POST`
- Path: `/api/ai/jobs/kill_selected`
- Authentication: Admin required
- Summary: Kill Selected Ai Jobs
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/jobs/kill_selected_me`

- HTTP Method: `POST`
- Path: `/api/ai/jobs/kill_selected_me`
- Authentication: 必須
- Summary: Kill Selected My Ai Jobs
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/jobs/me`

- HTTP Method: `GET`
- Path: `/api/ai/jobs/me`
- Authentication: 必須
- Summary: List My Ai Jobs
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/ai/jobs/{job_id}`

- HTTP Method: `GET`
- Path: `/api/ai/jobs/{job_id}`
- Authentication: 任意
- Summary: Get Ai Job Status
- Request Example:
```json
{
  "job_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/logs/me`

- HTTP Method: `GET`
- Path: `/api/ai/logs/me`
- Authentication: 必須
- Summary: Get My Ai Logs
- Request Example:
```json
{
  "limit": 50
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/memory/backfill`

- HTTP Method: `POST`
- Path: `/api/ai/memory/backfill`
- Authentication: Not required
- Summary: Backfill Ai Memory From Logs
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/memory/items`

- HTTP Method: `GET`
- Path: `/api/ai/memory/items`
- Authentication: Not required
- Summary: List Ai Memory Items
- Request Example:
```json
{
  "scope": "global",
  "scope_id": 1,
  "include_inactive": false,
  "limit": 50
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/ai/memory/items/{memory_id}`

- HTTP Method: `DELETE`
- Path: `/api/ai/memory/items/{memory_id}`
- Authentication: Not required
- Summary: Delete Ai Memory Item
- Request Example:
```json
{
  "memory_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `PATCH /api/ai/memory/items/{memory_id}/deactivate`

- HTTP Method: `PATCH`
- Path: `/api/ai/memory/items/{memory_id}/deactivate`
- Authentication: Not required
- Summary: Deactivate Ai Memory Item
- Request Example:
```json
{
  "memory_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/novel/addon/checkout`

- HTTP Method: `POST`
- Path: `/api/ai/novel/addon/checkout`
- Authentication: 必須
- Summary: Create Ai Novel Addon Checkout
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 402 Payment Required, 422 Validation Error, 500 Internal Server Error

### `POST /api/ai/novels/addon/checkout`

- HTTP Method: `POST`
- Path: `/api/ai/novels/addon/checkout`
- Authentication: 必須
- Summary: Create Ai Novel Addon Checkout
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 402 Payment Required, 422 Validation Error, 500 Internal Server Error

### `GET /api/ai/novels/auto-fill`

- HTTP Method: `GET`
- Path: `/api/ai/novels/auto-fill`
- Authentication: Not required
- Summary: Auto Fill Ai Novel Inputs
- Request Example:
```json
{
  "query": "string",
  "characters": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/novels/auto-fill`

- HTTP Method: `POST`
- Path: `/api/ai/novels/auto-fill`
- Authentication: Not required
- Summary: Auto Fill Ai Novel Inputs Post
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/novels/draft`

- HTTP Method: `GET`
- Path: `/api/ai/novels/draft`
- Authentication: 必須
- Summary: Get Ai Novel Draft
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/novels/draft`

- HTTP Method: `POST`
- Path: `/api/ai/novels/draft`
- Authentication: 必須
- Summary: Save Ai Novel Draft
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/novels/drafts`

- HTTP Method: `GET`
- Path: `/api/ai/novels/drafts`
- Authentication: 必須
- Summary: List Ai Novel Drafts
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/novels/drafts`

- HTTP Method: `POST`
- Path: `/api/ai/novels/drafts`
- Authentication: 必須
- Summary: Create Ai Novel Draft
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/ai/novels/drafts/{draft_id}`

- HTTP Method: `DELETE`
- Path: `/api/ai/novels/drafts/{draft_id}`
- Authentication: 必須
- Summary: Delete Ai Novel Draft
- Request Example:
```json
{
  "draft_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/novels/drafts/{draft_id}`

- HTTP Method: `GET`
- Path: `/api/ai/novels/drafts/{draft_id}`
- Authentication: 必須
- Summary: Get Ai Novel Draft Slot
- Request Example:
```json
{
  "draft_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `PUT /api/ai/novels/drafts/{draft_id}`

- HTTP Method: `PUT`
- Path: `/api/ai/novels/drafts/{draft_id}`
- Authentication: 必須
- Summary: Update Ai Novel Draft
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/novels/generate`

- HTTP Method: `POST`
- Path: `/api/ai/novels/generate`
- Authentication: Not required
- Summary: Generate Ai Novel
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/ai/novels/generate_job`

- HTTP Method: `POST`
- Path: `/api/ai/novels/generate_job`
- Authentication: Not required
- Summary: Create Ai Novel Job
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/ai/novels/remaining`

- HTTP Method: `GET`
- Path: `/api/ai/novels/remaining`
- Authentication: 任意
- Summary: Get Ai Novel Remaining
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/ai/novels/revision-target`

- HTTP Method: `POST`
- Path: `/api/ai/novels/revision-target`
- Authentication: Not required
- Summary: Locate Ai Novel Revision Target
- Request Example:
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
- Response Example:
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
- Common Errors: 422 Validation Error

### `POST /api/ai/novels/story-agent`

- HTTP Method: `POST`
- Path: `/api/ai/novels/story-agent`
- Authentication: 任意
- Summary: Generate Story Agent Reply
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error, 502 Bad Gateway

### `POST /api/ai/summary_candidates`

- HTTP Method: `POST`
- Path: `/api/ai/summary_candidates`
- Authentication: 必須
- Summary: Generate Summary Candidates
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/ai/tag_candidates`

- HTTP Method: `POST`
- Path: `/api/ai/tag_candidates`
- Authentication: 必須
- Summary: Generate Tag Candidates
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/ai/title_candidate`

- HTTP Method: `POST`
- Path: `/api/ai/title_candidate`
- Authentication: 必須
- Summary: Generate Title Candidate
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/ai/title_candidates`

- HTTP Method: `POST`
- Path: `/api/ai/title_candidates`
- Authentication: 必須
- Summary: Generate Title Candidates
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/i18n/dictionary/{target_lang}`

- HTTP Method: `GET`
- Path: `/api/i18n/dictionary/{target_lang}`
- Authentication: Not required
- Summary: I18N Dictionary
- Request Example:
```json
{
  "target_lang": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/i18n/translate`

- HTTP Method: `POST`
- Path: `/api/i18n/translate`
- Authentication: Not required
- Summary: I18N Translate
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

## Admin / SEO / Indexing

### `GET /api/admin/ai-chat/token-consumers/timeline`

- HTTP Method: `GET`
- Path: `/api/admin/ai-chat/token-consumers/timeline`
- Authentication: Admin required
- Summary: Admin Ai Chat Token Consumers Timeline
- Request Example:
```json
{
  "days": 30,
  "limit": 20
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/admin/ai/logs`

- HTTP Method: `GET`
- Path: `/api/admin/ai/logs`
- Authentication: Admin required
- Summary: Admin Get Ai Logs
- Request Example:
```json
{
  "limit": 200
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/admin/auth/login`

- HTTP Method: `POST`
- Path: `/api/admin/auth/login`
- Authentication: Admin required
- Summary: Admin Login
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 401 Unauthorized, 422 Validation Error, 500 Internal Server Error

### `POST /api/admin/auth/logout`

- HTTP Method: `POST`
- Path: `/api/admin/auth/logout`
- Authentication: Admin required
- Summary: Admin Logout
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/admin/auth/me`

- HTTP Method: `GET`
- Path: `/api/admin/auth/me`
- Authentication: Admin required
- Summary: Admin Me
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: 401 Unauthorized

### `GET /api/admin/authors/{author_user_id}/payout_profile`

- HTTP Method: `GET`
- Path: `/api/admin/authors/{author_user_id}/payout_profile`
- Authentication: Admin required
- Summary: Admin Author Payout Profile
- Request Example:
```json
{
  "author_user_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `DELETE /api/admin/board/posts/{post_id}`

- HTTP Method: `DELETE`
- Path: `/api/admin/board/posts/{post_id}`
- Authentication: Admin required
- Summary: Admin Delete Board Post
- Request Example:
```json
{
  "post_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/admin/contact/messages`

- HTTP Method: `GET`
- Path: `/api/admin/contact/messages`
- Authentication: Admin required
- Summary: Admin List Contact Messages
- Request Example:
```json
{
  "limit": 50
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/admin/contact/messages`

- HTTP Method: `POST`
- Path: `/api/admin/contact/messages`
- Authentication: Admin required
- Summary: Admin Create Contact Message
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/admin/email-test-all-users`

- HTTP Method: `POST`
- Path: `/api/admin/email-test-all-users`
- Authentication: Admin required
- Summary: Admin Send Test Email All Users
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request

### `GET /api/admin/i18n/jobs`

- HTTP Method: `GET`
- Path: `/api/admin/i18n/jobs`
- Authentication: Admin required
- Summary: Admin List I18N Jobs
- Request Example:
```json
{
  "limit": 20
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/admin/i18n/jobs/start`

- HTTP Method: `POST`
- Path: `/api/admin/i18n/jobs/start`
- Authentication: Admin required
- Summary: Admin Start I18N Job
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/admin/i18n/jobs/{job_id}`

- HTTP Method: `GET`
- Path: `/api/admin/i18n/jobs/{job_id}`
- Authentication: Admin required
- Summary: Admin I18N Job Status
- Request Example:
```json
{
  "job_id": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/admin/i18n/jobs/{job_id}/cancel`

- HTTP Method: `POST`
- Path: `/api/admin/i18n/jobs/{job_id}/cancel`
- Authentication: Admin required
- Summary: Admin Cancel I18N Job
- Request Example:
```json
{
  "job_id": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/admin/i18n/retranslate_remaining`

- HTTP Method: `POST`
- Path: `/api/admin/i18n/retranslate_remaining`
- Authentication: Admin required
- Summary: Admin Retranslate Remaining I18N
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `DELETE /api/admin/indexing/carryover`

- HTTP Method: `DELETE`
- Path: `/api/admin/indexing/carryover`
- Authentication: Admin required
- Summary: Admin Indexing Carryover Clear
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `GET /api/admin/indexing/carryover`

- HTTP Method: `GET`
- Path: `/api/admin/indexing/carryover`
- Authentication: Admin required
- Summary: Admin Indexing Carryover
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/admin/indexing/submit`

- HTTP Method: `POST`
- Path: `/api/admin/indexing/submit`
- Authentication: Admin required
- Summary: Admin Indexing Submit
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/admin/indexing/urls`

- HTTP Method: `GET`
- Path: `/api/admin/indexing/urls`
- Authentication: Admin required
- Summary: Admin Indexing Urls
- Request Example:
```json
{
  "limit": 1000,
  "inspect": false
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/admin/indexnow/submit`

- HTTP Method: `POST`
- Path: `/api/admin/indexnow/submit`
- Authentication: Admin required
- Summary: Admin Indexnow Submit
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error, 500 Internal Server Error

### `GET /api/admin/payouts`

- HTTP Method: `GET`
- Path: `/api/admin/payouts`
- Authentication: Admin required
- Summary: Admin List Payouts
- Request Example:
```json
{
  "status": "string",
  "limit": 50
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/admin/payouts/generate`

- HTTP Method: `POST`
- Path: `/api/admin/payouts/generate`
- Authentication: Admin required
- Summary: Generate Payouts
- Request Example:
```json
{
  "period": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/admin/payouts/preview`

- HTTP Method: `GET`
- Path: `/api/admin/payouts/preview`
- Authentication: Admin required
- Summary: Preview Payouts
- Request Example:
```json
{
  "period": "string"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `GET /api/admin/payouts/timeline`

- HTTP Method: `GET`
- Path: `/api/admin/payouts/timeline`
- Authentication: Admin required
- Summary: Admin Payouts Timeline
- Request Example:
```json
{
  "days": 90
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `POST /api/admin/payouts/{payout_id}/mark_failed`

- HTTP Method: `POST`
- Path: `/api/admin/payouts/{payout_id}/mark_failed`
- Authentication: Admin required
- Summary: Mark Payout Failed
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `POST /api/admin/payouts/{payout_id}/mark_paid`

- HTTP Method: `POST`
- Path: `/api/admin/payouts/{payout_id}/mark_paid`
- Authentication: Admin required
- Summary: Mark Payout Paid
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/admin/seo-pages`

- HTTP Method: `GET`
- Path: `/api/admin/seo-pages`
- Authentication: Admin required
- Summary: Admin List Seo Pages
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: None / not declared in OpenAPI

### `POST /api/admin/seo-pages`

- HTTP Method: `POST`
- Path: `/api/admin/seo-pages`
- Authentication: Admin required
- Summary: Admin Create Seo Page
- Request Example:
```json
{
  "example_key": "value"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/admin/seo-pages/{page_id}`

- HTTP Method: `GET`
- Path: `/api/admin/seo-pages/{page_id}`
- Authentication: Admin required
- Summary: Admin Get Seo Page
- Request Example:
```json
{
  "page_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `PUT /api/admin/seo-pages/{page_id}`

- HTTP Method: `PUT`
- Path: `/api/admin/seo-pages/{page_id}`
- Authentication: Admin required
- Summary: Admin Update Seo Page
- Request Example:
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
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 404 Not Found, 422 Validation Error

### `GET /api/admin/supports/timeline`

- HTTP Method: `GET`
- Path: `/api/admin/supports/timeline`
- Authentication: Admin required
- Summary: Admin Supports Timeline
- Request Example:
```json
{
  "days": 30,
  "limit": 10,
  "by": "author"
}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `POST /api/admin/translations/backfill`

- HTTP Method: `POST`
- Path: `/api/admin/translations/backfill`
- Authentication: Admin required
- Summary: Admin Backfill Translations
- Request Example:
```json
{}
```
- Response Example:
```json
"value"
```
- Common Errors: 400 Bad Request, 422 Validation Error

### `GET /api/admin/users`

- HTTP Method: `GET`
- Path: `/api/admin/users`
- Authentication: Admin required
- Summary: Admin List Users
- Request Example:
```json
{
  "limit": 50,
  "offset": 0
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error

### `DELETE /api/admin/users/{user_id}`

- HTTP Method: `DELETE`
- Path: `/api/admin/users/{user_id}`
- Authentication: Admin required
- Summary: Admin Delete User
- Request Example:
```json
{
  "user_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 404 Not Found, 422 Validation Error

### `GET /api/admin/users/{user_id}/novels`

- HTTP Method: `GET`
- Path: `/api/admin/users/{user_id}/novels`
- Authentication: Admin required
- Summary: Admin List User Novels
- Request Example:
```json
{
  "user_id": 1
}
```
- Response Example:
```json
"value"
```
- Common Errors: 422 Validation Error
