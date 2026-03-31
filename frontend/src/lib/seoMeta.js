const DEFAULT_OG_TYPE = "website";
const DEFAULT_TWITTER_CARD = "summary_large_image";
const MAX_DESCRIPTION_LENGTH = 140;

function asText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

export function buildSeoDescription(...candidates) {
  for (const candidate of candidates) {
    const clean = asText(candidate);
    if (!clean) continue;
    if (clean.length <= MAX_DESCRIPTION_LENGTH) return clean;
    return `${clean.slice(0, MAX_DESCRIPTION_LENGTH - 1)}…`;
  }
  return "";
}

function ensureMetaByName(name) {
  let el = document.querySelector(`meta[name="${name}"]`);
  let created = false;
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute("name", name);
    document.head.appendChild(el);
    created = true;
  }
  return { el, created };
}

function ensureMetaByProperty(property) {
  let el = document.querySelector(`meta[property="${property}"]`);
  let created = false;
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute("property", property);
    document.head.appendChild(el);
    created = true;
  }
  return { el, created };
}

function ensureCanonical() {
  let el = document.querySelector('link[rel="canonical"]');
  let created = false;
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
    created = true;
  }
  return { el, created };
}

function toAbsoluteUrl(pathOrUrl) {
  const value = String(pathOrUrl || "").trim();
  if (!value) return "";
  try {
    return new URL(value, window.location.origin).toString();
  } catch {
    return "";
  }
}

function rememberAttr(target, attr) {
  return {
    attr,
    had: target.hasAttribute(attr),
    value: target.getAttribute(attr),
  };
}

function restoreAttr(target, state) {
  if (!target || !state) return;
  if (!state.had) {
    target.removeAttribute(state.attr);
  } else if (state.value == null) {
    target.removeAttribute(state.attr);
  } else {
    target.setAttribute(state.attr, state.value);
  }
}

export function applySeoMeta({
  title,
  description,
  canonicalPath,
  ogType = DEFAULT_OG_TYPE,
  imageUrl,
  robots = "index,follow",
  twitterCard = DEFAULT_TWITTER_CARD,
  jsonLd = [],
}) {
  if (typeof document === "undefined" || typeof window === "undefined") {
    return () => {};
  }

  const cleanTitle = asText(title);
  const cleanDescription = buildSeoDescription(description);
  const canonicalUrl = toAbsoluteUrl(canonicalPath || window.location.href);
  const ogImage = toAbsoluteUrl(imageUrl);

  const previousTitle = document.title;

  const { el: descMeta, created: descCreated } = ensureMetaByName("description");
  const { el: robotsMeta, created: robotsCreated } = ensureMetaByName("robots");
  const { el: googlebotMeta, created: googlebotCreated } = ensureMetaByName("googlebot");
  const { el: bingbotMeta, created: bingbotCreated } = ensureMetaByName("bingbot");

  const { el: canonicalLink, created: canonicalCreated } = ensureCanonical();

  const { el: ogTitleMeta, created: ogTitleCreated } = ensureMetaByProperty("og:title");
  const { el: ogDescMeta, created: ogDescCreated } = ensureMetaByProperty("og:description");
  const { el: ogUrlMeta, created: ogUrlCreated } = ensureMetaByProperty("og:url");
  const { el: ogTypeMeta, created: ogTypeCreated } = ensureMetaByProperty("og:type");
  const { el: ogImageMeta, created: ogImageCreated } = ensureMetaByProperty("og:image");

  const { el: twCardMeta, created: twCardCreated } = ensureMetaByName("twitter:card");
  const { el: twTitleMeta, created: twTitleCreated } = ensureMetaByName("twitter:title");
  const { el: twDescMeta, created: twDescCreated } = ensureMetaByName("twitter:description");
  const { el: twImageMeta, created: twImageCreated } = ensureMetaByName("twitter:image");

  const states = [
    [descMeta, rememberAttr(descMeta, "content"), descCreated],
    [robotsMeta, rememberAttr(robotsMeta, "content"), robotsCreated],
    [googlebotMeta, rememberAttr(googlebotMeta, "content"), googlebotCreated],
    [bingbotMeta, rememberAttr(bingbotMeta, "content"), bingbotCreated],
    [canonicalLink, rememberAttr(canonicalLink, "href"), canonicalCreated],
    [ogTitleMeta, rememberAttr(ogTitleMeta, "content"), ogTitleCreated],
    [ogDescMeta, rememberAttr(ogDescMeta, "content"), ogDescCreated],
    [ogUrlMeta, rememberAttr(ogUrlMeta, "content"), ogUrlCreated],
    [ogTypeMeta, rememberAttr(ogTypeMeta, "content"), ogTypeCreated],
    [ogImageMeta, rememberAttr(ogImageMeta, "content"), ogImageCreated],
    [twCardMeta, rememberAttr(twCardMeta, "content"), twCardCreated],
    [twTitleMeta, rememberAttr(twTitleMeta, "content"), twTitleCreated],
    [twDescMeta, rememberAttr(twDescMeta, "content"), twDescCreated],
    [twImageMeta, rememberAttr(twImageMeta, "content"), twImageCreated],
  ];

  if (cleanTitle) document.title = cleanTitle;
  descMeta.setAttribute("content", cleanDescription);
  robotsMeta.setAttribute("content", robots);
  googlebotMeta.setAttribute("content", robots);
  bingbotMeta.setAttribute("content", robots);

  canonicalLink.setAttribute("href", canonicalUrl);

  ogTitleMeta.setAttribute("content", cleanTitle);
  ogDescMeta.setAttribute("content", cleanDescription);
  ogUrlMeta.setAttribute("content", canonicalUrl);
  ogTypeMeta.setAttribute("content", asText(ogType) || DEFAULT_OG_TYPE);
  if (ogImage) ogImageMeta.setAttribute("content", ogImage);
  else ogImageMeta.removeAttribute("content");

  twCardMeta.setAttribute("content", asText(twitterCard) || DEFAULT_TWITTER_CARD);
  twTitleMeta.setAttribute("content", cleanTitle);
  twDescMeta.setAttribute("content", cleanDescription);
  if (ogImage) twImageMeta.setAttribute("content", ogImage);
  else twImageMeta.removeAttribute("content");

  const jsonLdScripts = [];
  if (Array.isArray(jsonLd)) {
    for (const obj of jsonLd) {
      if (!obj || typeof obj !== "object") continue;
      const script = document.createElement("script");
      script.setAttribute("type", "application/ld+json");
      script.textContent = JSON.stringify(obj);
      script.setAttribute("data-seo-jsonld", "1");
      document.head.appendChild(script);
      jsonLdScripts.push(script);
    }
  }

  return () => {
    document.title = previousTitle;
    for (const [el, state, created] of states) {
      if (!el) continue;
      if (created) {
        el.remove();
      } else {
        restoreAttr(el, state);
      }
    }
    for (const script of jsonLdScripts) {
      script.remove();
    }
  };
}
