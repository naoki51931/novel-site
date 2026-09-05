import json
import os
from pathlib import Path


def _env_flag(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: str) -> float:
    raw = (os.getenv(name, default) or default).strip()
    try:
        return float(raw)
    except Exception:
        return float(default)


BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(
    os.getenv(
        "STATIC_DIR",
        "/app/static" if Path("/app/static").exists() else str(BASE_DIR / "static"),
    )
)
EPISODE_IMAGE_DIR = os.getenv(
    "EPISODE_IMAGE_DIR",
    str(STATIC_DIR / "episode_images"),
)
AI_CHAT_CHARACTER_IMAGE_DIR = os.getenv(
    "AI_CHAT_CHARACTER_IMAGE_DIR",
    str(STATIC_DIR / "ai_chat_character_images"),
)
AI_CHAT_MESSAGE_IMAGE_DIR = os.getenv(
    "AI_CHAT_MESSAGE_IMAGE_DIR",
    str(STATIC_DIR / "ai_chat_message_images"),
)
BLOG_IMAGE_DIR = os.getenv(
    "BLOG_IMAGE_DIR",
    str(STATIC_DIR / "blog_images"),
)
COVER_UPLOAD_DIR = os.getenv("COVER_UPLOAD_DIR", "/app/uploads/covers")
UPLOADS_DIR = Path(COVER_UPLOAD_DIR).resolve().parent

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 2
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES = int(
    os.getenv("REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES", "10")
)

FORCE_ALL_PREMIUM = os.getenv("FORCE_ALL_PREMIUM", "0") == "1"
FORCE_PREMIUM_USERNAMES = {
    s.strip().lower()
    for s in (os.getenv("FORCE_PREMIUM_USERNAMES", "") or "").split(",")
    if s.strip()
}
PREMIUM_REVALIDATE_DAYS = int(os.getenv("PREMIUM_REVALIDATE_DAYS", "30"))
AGE_RESTRICTION_DISABLED = os.getenv("AGE_RESTRICTION_DISABLED", "0") == "1"

STRIPE_USE_TEST = _env_flag("STRIPE_USE_TEST", "0")
if STRIPE_USE_TEST:
    STRIPE_SECRET_KEY = os.getenv("STRIPE_TEST_SECRET_KEY", "") or os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_TEST_WEBHOOK_SECRET", "") or os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID = os.getenv("STRIPE_TEST_PRICE_ID", "") or os.getenv("STRIPE_PRICE_ID", "")
    STRIPE_PRICE_ID_1000 = os.getenv("STRIPE_TEST_PRICE_ID_1000", "") or os.getenv("STRIPE_PRICE_ID_1000", "") or STRIPE_PRICE_ID
    STRIPE_PRICE_ID_3000 = os.getenv("STRIPE_TEST_PRICE_ID_3000", "") or os.getenv("STRIPE_PRICE_ID_3000", "")
    STRIPE_PRICE_ID_5000 = os.getenv("STRIPE_TEST_PRICE_ID_5000", "") or os.getenv("STRIPE_PRICE_ID_5000", "")
else:
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
    STRIPE_PRICE_ID_1000 = os.getenv("STRIPE_PRICE_ID_1000", "") or STRIPE_PRICE_ID
    STRIPE_PRICE_ID_3000 = os.getenv("STRIPE_PRICE_ID_3000", "")
    STRIPE_PRICE_ID_5000 = os.getenv("STRIPE_PRICE_ID_5000", "")
PLATFORM_FEE_RATE = float(os.getenv("PLATFORM_FEE_RATE", "0.2"))
MOON_ARCANA_ORIGIN = (os.getenv("MOON_ARCANA_ORIGIN", "https://moon-arcana.com") or "").strip().rstrip("/")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "")
ADMIN_JWT_EXPIRES_MINUTES = int(os.getenv("ADMIN_JWT_EXPIRES_MINUTES", "120"))
ADMIN_COOKIE_SECURE = os.getenv("ADMIN_COOKIE_SECURE", "1") == "1"
ADMIN_CSRF_COOKIE_NAME = "admin_csrf_token"
ADMIN_LOGIN_RATE_LIMIT_WINDOW_SEC = max(60, int(os.getenv("ADMIN_LOGIN_RATE_LIMIT_WINDOW_SEC", "900") or "900"))
ADMIN_LOGIN_RATE_LIMIT_MAX_FAILURES = max(1, int(os.getenv("ADMIN_LOGIN_RATE_LIMIT_MAX_FAILURES", "5") or "5"))
PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SEC = max(60, int(os.getenv("PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SEC", "900") or "900"))
PUBLIC_CONTACT_RATE_LIMIT_MAX_REQUESTS = max(1, int(os.getenv("PUBLIC_CONTACT_RATE_LIMIT_MAX_REQUESTS", "5") or "5"))
PUBLIC_CONTACT_DUPLICATE_WINDOW_SEC = max(60, int(os.getenv("PUBLIC_CONTACT_DUPLICATE_WINDOW_SEC", "300") or "300"))
REGISTER_EMAIL_START_RATE_LIMIT_WINDOW_SEC = max(
    60, int(os.getenv("REGISTER_EMAIL_START_RATE_LIMIT_WINDOW_SEC", "900") or "900")
)
REGISTER_EMAIL_START_RATE_LIMIT_MAX_REQUESTS = max(
    1, int(os.getenv("REGISTER_EMAIL_START_RATE_LIMIT_MAX_REQUESTS", "5") or "5")
)
REGISTER_EMAIL_START_COOLDOWN_SEC = max(
    30, int(os.getenv("REGISTER_EMAIL_START_COOLDOWN_SEC", "60") or "60")
)
LOGIN_START_FAILURE_WINDOW_SEC = max(60, int(os.getenv("LOGIN_START_FAILURE_WINDOW_SEC", "900") or "900"))
LOGIN_START_MAX_FAILURES = max(1, int(os.getenv("LOGIN_START_MAX_FAILURES", "5") or "5"))
LOGIN_START_CODE_COOLDOWN_SEC = max(30, int(os.getenv("LOGIN_START_CODE_COOLDOWN_SEC", "60") or "60"))
AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC = max(30, int(os.getenv("AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC", "60") or "60"))
AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS", "20") or "20")
)
AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS", "8") or "8")
)
AI_CHAT_IMAGE_RATE_LIMIT_WINDOW_SEC = max(60, int(os.getenv("AI_CHAT_IMAGE_RATE_LIMIT_WINDOW_SEC", "300") or "300"))
AI_CHAT_IMAGE_RATE_LIMIT_USER_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_IMAGE_RATE_LIMIT_USER_MAX_REQUESTS", "5") or "5")
)
AI_CHAT_IMAGE_RATE_LIMIT_GUEST_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_IMAGE_RATE_LIMIT_GUEST_MAX_REQUESTS", "2") or "2")
)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
BACKEND_ORIGIN = os.getenv("BACKEND_ORIGIN", "http://localhost:8000")
INDEXNOW_ENABLED = _env_flag("INDEXNOW_ENABLED", "0")
INDEXNOW_KEY = (os.getenv("INDEXNOW_KEY", "") or "").strip()
INDEXNOW_HOST = (os.getenv("INDEXNOW_HOST", "") or "").strip().lower()
INDEXNOW_ENDPOINT = (
    os.getenv("INDEXNOW_ENDPOINT", "https://api.indexnow.org/indexnow") or "https://api.indexnow.org/indexnow"
).strip()
SITE_KEY_DEFAULT = (os.getenv("SITE_KEY_DEFAULT", "main") or "main").strip().lower()
SITE_KEY_ALLOWED = {
    s.strip().lower()
    for s in (os.getenv("SITE_KEY_ALLOWED", "main,romance,history") or "").split(",")
    if s.strip()
}
if SITE_KEY_DEFAULT not in SITE_KEY_ALLOWED:
    SITE_KEY_ALLOWED.add(SITE_KEY_DEFAULT)

_site_host_map_raw = (os.getenv("SITE_HOST_MAP_JSON", "") or "").strip()
SITE_HOST_MAP: dict[str, str] = {}
if _site_host_map_raw:
    try:
        parsed = json.loads(_site_host_map_raw)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                host = str(k or "").strip().lower()
                site = str(v or "").strip().lower()
                if host and site:
                    SITE_HOST_MAP[host] = site
    except Exception as e:
        print("[site] SITE_HOST_MAP_JSON parse failed:", repr(e))

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
X_OAUTH_CONSUMER_KEY = os.getenv("X_OAUTH_CONSUMER_KEY", "")
X_OAUTH_CONSUMER_SECRET = os.getenv("X_OAUTH_CONSUMER_SECRET", "")
OAUTH_STATE_EXPIRE_MINUTES = int(os.getenv("OAUTH_STATE_EXPIRE_MINUTES", "10"))

TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "").strip().lower()
TRANSLATION_MODEL_TEXT = os.getenv("TRANSLATION_MODEL_TEXT", "").strip()
NOVEL_TRANSLATION_ORIGINAL_ONLY = os.getenv("NOVEL_TRANSLATION_ORIGINAL_ONLY", "0") == "1"
NOVEL_TRANSLATION_JA_EN_ONLY = os.getenv("NOVEL_TRANSLATION_JA_EN_ONLY", "0") == "1"
NOVEL_TRANSLATION_ALL_LANGUAGES = os.getenv("NOVEL_TRANSLATION_ALL_LANGUAGES", "0") == "1"
try:
    TRANSLATION_AI_TIMEOUT_SECONDS = float(os.getenv("TRANSLATION_AI_TIMEOUT_SECONDS", "120") or 120)
except Exception:
    TRANSLATION_AI_TIMEOUT_SECONDS = 120.0
TRANSLATION_AI_TIMEOUT_SECONDS = max(15.0, min(900.0, TRANSLATION_AI_TIMEOUT_SECONDS))
try:
    AI_CHAT_TEXT_TIMEOUT_SECONDS = float(os.getenv("AI_CHAT_TEXT_TIMEOUT_SECONDS", "600") or 600)
except Exception:
    AI_CHAT_TEXT_TIMEOUT_SECONDS = 600.0
AI_CHAT_TEXT_TIMEOUT_SECONDS = max(15.0, min(900.0, AI_CHAT_TEXT_TIMEOUT_SECONDS))
AUTO_TRANSLATION_REQUIRED = os.getenv("AUTO_TRANSLATION_REQUIRED", "0") == "1"
DAILY_TRANSLATION_BOT_ENABLED = os.getenv("DAILY_TRANSLATION_BOT_ENABLED", "1") == "1"
DAILY_TRANSLATION_BOT_INTERVAL_SECONDS = max(
    3600,
    int(os.getenv("DAILY_TRANSLATION_BOT_INTERVAL_SECONDS", "86400") or 86400),
)
DAILY_TRANSLATION_BOT_MAX_NOVELS = max(
    0,
    min(5000, int(os.getenv("DAILY_TRANSLATION_BOT_MAX_NOVELS", "200") or 200)),
)
DAILY_TRANSLATION_BOT_MAX_EPISODES = max(
    0,
    min(10000, int(os.getenv("DAILY_TRANSLATION_BOT_MAX_EPISODES", "400") or 400)),
)
DAILY_TRANSLATION_BOT_ONLY_PUBLIC = os.getenv("DAILY_TRANSLATION_BOT_ONLY_PUBLIC", "0") == "1"
DAILY_TRANSLATION_BOT_SITE_KEY = (os.getenv("DAILY_TRANSLATION_BOT_SITE_KEY", "") or "").strip().lower() or None
AI_CHAT_FREE_TOKENS = int(os.getenv("AI_CHAT_FREE_TOKENS", "2000000"))
AI_CHAT_GUEST_TOKENS = int(os.getenv("AI_CHAT_GUEST_TOKENS", "2000000"))
AI_CHAT_BLOCK_TOKENS = int(os.getenv("AI_CHAT_BLOCK_TOKENS", "2000000"))
AI_CHAT_BLOCK_PRICE_YEN = int(os.getenv("AI_CHAT_BLOCK_PRICE_YEN", "1000"))
AI_CHAT_PREMIUM_INCLUDED_BLOCKS = max(0, int(os.getenv("AI_CHAT_PREMIUM_INCLUDED_BLOCKS", "1") or 1))
AI_CONSULTATION_FREE_TOKENS = int(os.getenv("AI_CONSULTATION_FREE_TOKENS", "200000"))
AI_CONSULTATION_GUEST_TOKENS = int(os.getenv("AI_CONSULTATION_GUEST_TOKENS", "50000"))
AI_CONSULTATION_PREMIUM_TOKENS = int(os.getenv("AI_CONSULTATION_PREMIUM_TOKENS", "2000000"))
MONTHLY_STRIPE_PREMIUM_SYNC_ENABLED = _env_flag("MONTHLY_STRIPE_PREMIUM_SYNC_ENABLED", "1")
MONTHLY_STRIPE_PREMIUM_SYNC_INTERVAL_SECONDS = max(3600, int(os.getenv("MONTHLY_STRIPE_PREMIUM_SYNC_INTERVAL_SECONDS", "86400") or 86400))
MONTHLY_STRIPE_PREMIUM_SYNC_DAY = max(1, min(28, int(os.getenv("MONTHLY_STRIPE_PREMIUM_SYNC_DAY", "1") or 1)))
MONTHLY_STRIPE_PREMIUM_SYNC_HOUR_UTC = max(0, min(23, int(os.getenv("MONTHLY_STRIPE_PREMIUM_SYNC_HOUR_UTC", "3") or 3)))
AI_CHAT_DEMO_BYPASS_USERNAME = os.getenv("AI_CHAT_DEMO_BYPASS_USERNAME", "demo02").strip()
try:
    AI_CHAT_TEMPERATURE = float(os.getenv("AI_CHAT_TEMPERATURE", "0.9") or 0.9)
except Exception:
    AI_CHAT_TEMPERATURE = 0.9
AI_CHAT_TEMPERATURE = max(0.0, min(2.0, AI_CHAT_TEMPERATURE))
try:
    AI_CHAT_TOP_P = float(os.getenv("AI_CHAT_TOP_P", "0.95") or 0.95)
except Exception:
    AI_CHAT_TOP_P = 0.95
AI_CHAT_TOP_P = max(0.0, min(1.0, AI_CHAT_TOP_P))
AI_CHAT_IMAGE_API_BASE_URL = os.getenv("AI_CHAT_IMAGE_API_BASE_URL", "").strip().rstrip("/")
AI_CHAT_IMAGE_API_KEY = os.getenv("AI_CHAT_IMAGE_API_KEY", "").strip()
AI_CHAT_IMAGE_MODEL_ID = os.getenv("AI_CHAT_IMAGE_MODEL_ID", "").strip()
AI_CHAT_IMAGE_NEGATIVE_PROMPT = os.getenv("AI_CHAT_IMAGE_NEGATIVE_PROMPT", "").strip()
AI_CHAT_IMAGE_TIMEOUT_SEC = float(os.getenv("AI_CHAT_IMAGE_TIMEOUT_SEC", "45"))
AI_CHAT_IMAGE_QUALITY_RETRY_ENABLED = os.getenv("AI_CHAT_IMAGE_QUALITY_RETRY_ENABLED", "1") == "1"
AI_CHAT_IMAGE_QUALITY_MIN_SCORE = float(os.getenv("AI_CHAT_IMAGE_QUALITY_MIN_SCORE", "42"))
AI_CHAT_IMAGE_QUALITY_MAX_RETRIES = max(0, min(10, int(os.getenv("AI_CHAT_IMAGE_QUALITY_MAX_RETRIES", "1"))))
AI_CHAT_IMAGE_QUALITY_SAMPLE_SIZE = max(1, min(4, int(os.getenv("AI_CHAT_IMAGE_QUALITY_SAMPLE_SIZE", "1"))))
AI_CHAT_IMAGE_MESSAGE_PREFIX = "__AI_CHAT_IMAGE_MSG__:"
AI_CHAT_IMAGE_OOM_RETRY_ENABLED = os.getenv("AI_CHAT_IMAGE_OOM_RETRY_ENABLED", "1") == "1"
AI_CHAT_IMAGE_OOM_RETRY_SCALE = float(os.getenv("AI_CHAT_IMAGE_OOM_RETRY_SCALE", "0.78"))
AI_CHAT_IMAGE_OOM_RETRY_STEPS = max(8, min(80, int(os.getenv("AI_CHAT_IMAGE_OOM_RETRY_STEPS", "28"))))
AI_CHAT_IMAGE_INIT_STRENGTH = max(0.1, min(0.95, float(os.getenv("AI_CHAT_IMAGE_INIT_STRENGTH", "0.75"))))
AI_CHAT_IMAGE_CAPTION_ENABLED = _env_flag("AI_CHAT_IMAGE_CAPTION_ENABLED", "1")
AI_CHAT_IMAGE_CAPTION_MODEL = (os.getenv("AI_CHAT_IMAGE_CAPTION_MODEL", "") or "").strip() or (os.getenv("OPENAI_MODEL_TEXT", "") or "").strip() or "gpt-4.1-mini"
AI_CHAT_IMAGE_CAPTION_MAX_OUTPUT_TOKENS = max(32, min(300, int(os.getenv("AI_CHAT_IMAGE_CAPTION_MAX_OUTPUT_TOKENS", "120") or 120)))
BOARD_NOTIFY_USERNAME = (os.getenv("BOARD_NOTIFY_USERNAME", "demo02") or "demo02").strip()
AI_CHAT_MEMORY_ENABLED = _env_flag("AI_CHAT_MEMORY_ENABLED", "1")
AI_CHAT_MEMORY_TOPK = max(1, min(20, int(os.getenv("AI_CHAT_MEMORY_TOPK", "12") or 12)))
AI_WEAVIATE_FEATURES_ENABLED = _env_flag("AI_WEAVIATE_FEATURES_ENABLED", "1")
AI_WEAVIATE_FEATURES_TOPK = max(1, min(12, int(os.getenv("AI_WEAVIATE_FEATURES_TOPK", "4") or 4)))
AI_NOVEL_ADDON_UNIT_GENERATIONS = int(os.getenv("AI_NOVEL_ADDON_UNIT_GENERATIONS", "80"))
AI_NOVEL_ADDON_PRICE_YEN = int(os.getenv("AI_NOVEL_ADDON_PRICE_YEN", "1000"))
AI_JOB_TIMEOUT_MINUTES = int(os.getenv("AI_JOB_TIMEOUT_MINUTES", "60") or 60)

RECOMMENDED_RECENT_VIEW_EXCLUDE_COUNT = max(
    0, int(os.getenv("RECOMMENDED_RECENT_VIEW_EXCLUDE_COUNT", "200") or 200)
)
RECOMMENDED_FOLLOWED_AUTHOR_BOOST = _env_float("RECOMMENDED_FOLLOWED_AUTHOR_BOOST", "8.0")
RECOMMENDED_CREATIVE_MATCH_BOOST = _env_float("RECOMMENDED_CREATIVE_MATCH_BOOST", "4.0")
RECOMMENDED_CREATIVE_MISMATCH_PENALTY = _env_float("RECOMMENDED_CREATIVE_MISMATCH_PENALTY", "-1.0")
RECOMMENDED_CREATIVE_PREFERENCE_THRESHOLD = max(
    0.5, min(0.95, _env_float("RECOMMENDED_CREATIVE_PREFERENCE_THRESHOLD", "0.6"))
)
