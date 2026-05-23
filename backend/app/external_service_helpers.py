import json
import os
import re
from functools import lru_cache
from urllib.parse import urlparse

import httpx

try:
    from google.cloud import recaptchaenterprise_v1  # type: ignore
    from google.cloud.recaptchaenterprise_v1 import Assessment as RecaptchaAssessment  # type: ignore
    from google.oauth2 import service_account as google_service_account  # type: ignore

    RECAPTCHA_ENTERPRISE_AVAILABLE = True
except Exception:
    recaptchaenterprise_v1 = None  # type: ignore
    RecaptchaAssessment = None  # type: ignore
    google_service_account = None  # type: ignore
    RECAPTCHA_ENTERPRISE_AVAILABLE = False

try:
    from janome.tokenizer import Tokenizer  # type: ignore
except Exception:
    Tokenizer = None


GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT = max(
    1, min(5000, int(os.getenv("GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT", "199") or "199"))
)
GOOGLE_INDEXING_CARRYOVER_TTL_SEC = max(
    86400,
    int(
        os.getenv(
            "GOOGLE_INDEXING_CARRYOVER_TTL_SEC",
            str(60 * 60 * 24 * 30),
        )
        or str(60 * 60 * 24 * 30)
    ),
)
GOOGLE_INDEXING_CARRYOVER_KEY = "queue:admin:indexing:carryover:v1"
RECAPTCHA_SECRET_KEY = (os.getenv("RECAPTCHA_SECRET_KEY", "") or "").strip()
RECAPTCHA_SITE_KEY = (
    os.getenv("RECAPTCHA_SITE_KEY", "")
    or os.getenv("VITE_RECAPTCHA_SITE_KEY", "")
).strip()
RECAPTCHA_PROJECT_ID = (
    os.getenv("RECAPTCHA_PROJECT_ID", "")
    or os.getenv("GOOGLE_CLOUD_PROJECT", "")
).strip()
RECAPTCHA_SERVICE_ACCOUNT_JSON = (os.getenv("RECAPTCHA_SERVICE_ACCOUNT_JSON", "") or "").strip()
RECAPTCHA_MIN_SCORE = float((os.getenv("RECAPTCHA_MIN_SCORE", "0.3") or "0.3").strip() or "0.3")
RECAPTCHA_ENTERPRISE_ENABLED = (
    (os.getenv("RECAPTCHA_ENTERPRISE_ENABLED", "1") or "1").strip() == "1"
    and RECAPTCHA_ENTERPRISE_AVAILABLE
    and bool(RECAPTCHA_SITE_KEY)
    and bool(RECAPTCHA_PROJECT_ID)
)
RECAPTCHA_ENABLED = ((os.getenv("RECAPTCHA_ENABLED", "1") or "1").strip() == "1") and bool(
    RECAPTCHA_SECRET_KEY
)


def _get_env_any(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


GOOGLE_CSE_API_KEY = _get_env_any(
    "GOOGLE_CSE_API_KEY",
    "GOOGLE_CUSTOM_SEARCH_API_KEY",
    "GOOGLE_CSE_KEY",
    "GOOGLE_API_KEY",
)
GOOGLE_CSE_CX = _get_env_any(
    "GOOGLE_CSE_CX",
    "GOOGLE_CUSTOM_SEARCH_CX",
    "GOOGLE_CUSTOM_SEARCH_ENGINE_ID",
    "GOOGLE_CSE_ENGINE_ID",
    "GOOGLE_CSE_ID",
)
GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL = _get_env_any(
    "GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL",
    "GOOGLE_SERVICE_ACCOUNT_EMAIL",
)
GOOGLE_INDEXING_PRIVATE_KEY = _get_env_any(
    "GOOGLE_INDEXING_PRIVATE_KEY",
    "GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY",
)
GOOGLE_INDEXING_PRIVATE_KEY_ID = _get_env_any(
    "GOOGLE_INDEXING_PRIVATE_KEY_ID",
    "GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID",
)
GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON = _get_env_any(
    "GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
)
GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON = _get_env_any(
    "GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
)
GOOGLE_SEARCH_CONSOLE_SITE_URL = _get_env_any(
    "GOOGLE_SEARCH_CONSOLE_SITE_URL",
    "GOOGLE_SEARCH_CONSOLE_PROPERTY_URI",
)

PREFERRED_CSE_HOSTS = (
    "wikipedia.org",
    "fandom.com",
    "atwiki.jp",
    "pixiv.net",
    "dic.pixiv.net",
)

JANOME_AVAILABLE = Tokenizer is not None
_janome_tokenizer = Tokenizer() if JANOME_AVAILABLE else None


@lru_cache(maxsize=1)
def _get_recaptcha_enterprise_client():
    if not RECAPTCHA_ENTERPRISE_ENABLED or recaptchaenterprise_v1 is None:
        return None

    cred_json = (
        RECAPTCHA_SERVICE_ACCOUNT_JSON
        or (os.getenv("GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON", "") or "").strip()
        or (os.getenv("GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON", "") or "").strip()
        or (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "") or "").strip()
    )
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    try:
        if cred_json and google_service_account is not None:
            info = json.loads(cred_json)
            creds = google_service_account.Credentials.from_service_account_info(info, scopes=scopes)
            return recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient(credentials=creds)
        return recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient()
    except Exception:
        return None


def verify_recaptcha_token(
    token: str,
    remote_ip: str | None = None,
    expected_action: str | None = None,
) -> bool:
    if not RECAPTCHA_ENABLED and not RECAPTCHA_ENTERPRISE_ENABLED:
        return True
    recaptcha_token = (token or "").strip()
    if not recaptcha_token:
        return False

    if RECAPTCHA_ENTERPRISE_ENABLED and recaptchaenterprise_v1 is not None and RecaptchaAssessment is not None:
        try:
            client = _get_recaptcha_enterprise_client()
            if client is None:
                raise RuntimeError("recaptcha enterprise client unavailable")
            event = recaptchaenterprise_v1.Event()
            event.site_key = RECAPTCHA_SITE_KEY
            event.token = recaptcha_token

            assessment = recaptchaenterprise_v1.Assessment()
            assessment.event = event

            request = recaptchaenterprise_v1.CreateAssessmentRequest(
                parent=f"projects/{RECAPTCHA_PROJECT_ID}",
                assessment=assessment,
            )
            response = client.create_assessment(request=request)

            token_props = getattr(response, "token_properties", None)
            if not token_props or not bool(getattr(token_props, "valid", False)):
                return False

            actual_action = str(getattr(token_props, "action", "") or "").strip()
            if expected_action and actual_action != expected_action:
                return False

            risk = getattr(response, "risk_analysis", None)
            score = getattr(risk, "score", None) if risk is not None else None
            if score is None:
                return False
            if float(score) < RECAPTCHA_MIN_SCORE:
                return False
            return True
        except Exception:
            pass

    payload: dict[str, str] = {
        "secret": RECAPTCHA_SECRET_KEY,
        "response": recaptcha_token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        res = httpx.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data=payload,
            timeout=8.0,
        )
        if res.status_code != 200:
            return False
        data = res.json()
        if not bool(data.get("success")):
            return False
        action = str(data.get("action") or "").strip()
        if expected_action and action and action != expected_action:
            return False
        score_raw = data.get("score")
        if score_raw is not None:
            try:
                if float(score_raw) < RECAPTCHA_MIN_SCORE:
                    return False
            except Exception:
                return False
        return True
    except Exception:
        return False


def _is_preferred_cse_host(url: str | None) -> bool:
    if not url:
        return False
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return any(h in host for h in PREFERRED_CSE_HOSTS)


def _build_auto_fill_snippets(items: list[dict]) -> tuple[str, str]:
    if not items:
        return ("", "")
    titles = [i.get("title", "").strip() for i in items if i.get("title")]
    titles = [t for t in titles if t]
    genre_append = " / ".join(titles[:3])

    lines = []
    for item in items:
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        if title and snippet:
            lines.append(f"- {title}: {snippet}")
        elif title:
            lines.append(f"- {title}")
        elif snippet:
            lines.append(f"- {snippet}")
        if sum(len(line) for line in lines) >= 1000:
            break
    characters_append = "\n".join(lines)
    if len(characters_append) > 1000:
        characters_append = characters_append[:1000].rstrip()
    return (genre_append, characters_append)


def _split_search_terms(query: str) -> list[str]:
    parts = re.split(r"[,/、\\n]+", query)
    terms = [p.strip() for p in parts if p.strip()]
    return terms[:3]


def _split_character_terms(text: str) -> list[str]:
    if not text:
        return []
    if not JANOME_AVAILABLE or _janome_tokenizer is None:
        parts = re.split(r"[\\s、,。.!?！？/]+", text)
        terms = [p.strip() for p in parts if p.strip()]
        return terms[:15]

    quoted_matches = re.findall(r'["“”]([^"“”]+)["“”]', text)
    protected = [s.strip() for s in quoted_matches if s.strip()]
    if protected:
        for s in quoted_matches:
            text = text.replace(s, " ")

    person_terms: list[str] = []
    sahen_terms: list[str] = []
    other_terms: list[str] = []
    seen: set[str] = set()
    for term in protected:
        if term in seen:
            continue
        seen.add(term)
        person_terms.append(term)
    for token in _janome_tokenizer.tokenize(text):
        surface = (token.surface or "").strip()
        if not surface:
            continue
        pos_parts = (token.part_of_speech or "").split(",")
        pos = pos_parts[0] if pos_parts else ""
        if pos != "名詞":
            continue
        if len(surface) == 1 and not surface.isalnum():
            continue
        if surface in seen:
            continue
        seen.add(surface)
        if len(pos_parts) >= 3 and pos_parts[1] == "固有名詞" and pos_parts[2] == "人名":
            person_terms.append(surface)
        elif len(pos_parts) >= 2 and pos_parts[1] == "固有名詞":
            person_terms.append(surface)
        elif len(pos_parts) >= 2 and pos_parts[1] == "サ変接続":
            sahen_terms.append(surface)
        else:
            other_terms.append(surface)

    ordered = person_terms + sahen_terms + other_terms
    return ordered[:15]


def _split_character_fullname_terms(text: str) -> list[str]:
    if not text:
        return []
    chunks = re.split(r"[,/、\n]+", str(text))
    out: list[str] = []
    seen: set[str] = set()

    def push(candidate: str) -> None:
        c = str(candidate or "").strip()
        if len(c) < 2 or c in seen:
            return
        seen.add(c)
        out.append(c)

    for chunk in chunks:
        raw = re.sub(r"\s+", " ", (chunk or "").strip())
        if not raw:
            continue
        cleaned = raw.replace('"', "").replace("“", "").replace("”", "").strip()
        if not cleaned:
            continue
        push(cleaned)
        tokens = [t for t in re.split(r"\s+", cleaned) if t]
        if len(tokens) >= 2:
            if len(tokens) >= 4 and len(tokens) % 2 == 0:
                for i in range(0, len(tokens), 2):
                    pair_spaced = f"{tokens[i]} {tokens[i + 1]}".strip()
                    pair_compact = f"{tokens[i]}{tokens[i + 1]}".strip()
                    push(pair_spaced)
                    push(pair_compact)
            for i in range(0, len(tokens) - 1):
                pair_spaced = f"{tokens[i]} {tokens[i + 1]}".strip()
                pair_compact = f"{tokens[i]}{tokens[i + 1]}".strip()
                push(pair_spaced)
                push(pair_compact)
            push("".join(tokens))
        else:
            push(cleaned)
        if len(out) >= 10:
            break
    return out
