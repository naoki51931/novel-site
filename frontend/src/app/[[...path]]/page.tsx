import type { Metadata } from "next";
import { headers } from "next/headers";
import ClientApp from "../../NextClientApp";

export const dynamic = "force-dynamic";

type SeoLang = "ja" | "en" | "zh-cn" | "zh-tw" | "ko";
type LocalizedText = string | Partial<Record<SeoLang, string>>;
type LocalizedKeywords = string[] | Partial<Record<SeoLang, string[]>>;

const SITE_NAME = "小説投稿サイトLexis（レクシー/レクシス）";
const DEFAULT_DESCRIPTION =
  "小説投稿サイトLexis（レクシー/レクシス）。誰でも小説を読めて、作品を投稿できます。恋愛・ファンタジー・SF・ホラーなど幅広いジャンルの作品を公開中。";
const BACKEND_ORIGIN = (
  process.env.NEXT_INTERNAL_BACKEND_ORIGIN ||
  process.env.BACKEND_ORIGIN ||
  "http://localhost:8000"
).replace(/\/+$/, "");
const STATIC_PAGE_SEO: Record<
  string,
  {
    title: LocalizedText;
    description: LocalizedText;
    absoluteTitle?: LocalizedText;
    ogType?: "website" | "book" | "article" | "profile";
    keywords?: LocalizedKeywords;
  }
> = {
  "/ranking": {
    title: "小説ランキング",
    description: "Lexisで読まれている人気小説ランキングです。注目作品を人気順に探せます。",
  },
  "/discover": {
    title: "小説を発見",
    description: "新しい作品や作者と出会える小説発見ページです。好みに合う作品を探せます。",
  },
  "/all": {
    title: "ジャンル別小説サイト一覧",
    description: "Lexisの小説投稿サイトとジャンル別サイトを一覧できます。",
  },
  "/authors": {
    title: "作者向け",
    description: "Lexisで小説を投稿したい作者向けの案内ページです。",
  },
  "/fanfic": {
    title: "二次創作小説",
    description: "二次創作小説を探せるページです。作品タグや新着作品から読みたい小説を見つけられます。",
  },
  "/board": {
    title: "掲示板",
    description: "Lexisの掲示板です。小説、創作、読書について交流できます。",
  },
  "/premium": {
    title: "プレミアム",
    description: "Lexisのプレミアム機能を確認できます。読書と創作をより便利に使えます。",
  },
  "/contact": {
    title: "お問い合わせ",
    description: "小説投稿サイトLexisへのお問い合わせページです。",
  },
  "/ai-novel": {
    title: {
      ja: "AI小説生成・小説生成AI・R18小説生成",
      en: "AI novel generator, story writing AI, and R18 draft support",
      "zh-cn": "支持 R18 的 AI 小说生成",
      "zh-tw": "支援 R18 的 AI 小說生成",
      ko: "R18 지원 AI 소설 생성",
    },
    absoluteTitle: {
      ja: "AI小説生成・小説生成AI・R18小説生成｜小説投稿サイトLexis（レクシー/レクシス）",
      en: "AI novel generator, story writing AI, and R18 draft support - Lexis",
      "zh-cn": "支持 R18 的 AI 小说生成 - Lexis",
      "zh-tw": "支援 R18 的 AI 小說生成 - Lexis",
      ko: "R18 지원 AI 소설 생성 - Lexis",
    },
    description: {
      ja: "LexisのAI小説生成ページです。プロット、登場人物、ジャンル、文体を指定して小説生成AIで物語を作成できます。R18小説生成、官能小説の下書き、続き生成、執筆支援にも対応しています。",
      en: "Use Lexis as an AI novel generator and story writing AI. Create plots, characters, genres, prose, episode continuations, and R18 or adult novel drafts with editing support.",
      "zh-cn": "这是 Lexis 的 AI 小说生成页面，支持普通故事创作、R18 小说草稿生成、续写与写作辅助。",
      "zh-tw": "這是 Lexis 的 AI 小說生成頁面，支援一般故事創作、R18 小說草稿生成、續寫與寫作輔助。",
      ko: "Lexis의 AI 소설 생성 페이지입니다. 일반 소설 작성, R18 초안 생성, 이어쓰기, 집필 보조를 지원합니다.",
    },
    keywords: {
      ja: [
        "AI小説",
        "AI小説生成",
        "小説生成AI",
        "AI小説メーカー",
        "AI小説作成",
        "AI物語生成",
        "R18小説生成",
        "官能小説生成",
        "AI 官能小説",
        "成人向け小説AI",
        "物語 生成",
        "プロット生成",
        "続き生成",
        "執筆支援",
      ],
      en: [
        "AI novel",
        "AI novel generator",
        "AI novel generation",
        "AI story generator",
        "story writing AI",
        "novel writing AI",
        "AI fiction writer",
        "R18 novel generation",
        "adult novel AI",
        "adult story generator",
        "story generator",
        "plot generator",
        "episode continuation generator",
        "writing assistant",
      ],
      "zh-cn": [
        "AI小说",
        "AI小说生成",
        "R18小说生成",
        "成人向小说AI",
        "故事生成",
        "写作辅助",
      ],
      "zh-tw": [
        "AI小說",
        "AI小說生成",
        "R18小說生成",
        "成人向小說AI",
        "故事生成",
        "寫作輔助",
      ],
      ko: [
        "AI 소설",
        "AI 소설 생성",
        "R18 소설 생성",
        "성인향 소설 AI",
        "스토리 생성",
        "집필 보조",
      ],
    },
  },
  "/en/ai-novel": {
    title: "AI novel generator, story writing AI, and R18 draft support",
    absoluteTitle: "AI novel generator, story writing AI, and R18 draft support - Lexis",
    description:
      "Use Lexis as an AI novel generator and story writing AI. Create plots, characters, genres, prose, episode continuations, and R18 or adult novel drafts with editing support.",
    keywords: [
      "AI novel",
      "AI novel generator",
      "AI novel generation",
      "AI story generator",
      "story writing AI",
      "novel writing AI",
      "AI fiction writer",
      "R18 novel generation",
      "adult novel AI",
      "adult story generator",
      "story generator",
      "plot generator",
      "episode continuation generator",
      "writing assistant",
    ],
  },
  "/ai_chat": {
    title: "AIチャット・キャラクターAIチャット・R18チャット",
    absoluteTitle: "AIチャット・キャラクターAIチャット・R18チャット｜小説投稿サイトLexis（レクシー/レクシス）",
    description:
      "LexisのAIチャットページです。キャラクター設定、性格、関係性を作成して会話できます。R18チャット、恋人AIチャット、会話ログからAI小説化する機能にも対応しています。",
    keywords: [
      "AIチャット",
      "キャラクターAIチャット",
      "R18チャット",
      "18禁チャット",
      "恋人AIチャット",
      "AI彼女",
      "AI彼氏",
      "会話AI",
      "AI小説化",
      "会話から小説生成",
    ],
  },
  "/en/ai_chat": {
    title: "AI chat, character AI chat, and R18 chat",
    absoluteTitle: "AI chat, character AI chat, and R18 chat - Lexis",
    description:
      "Use Lexis for AI chat with custom characters, personality settings, relationships, R18 chat options, girlfriend or boyfriend roleplay, and chat-to-novel writing support.",
    keywords: [
      "AI chat",
      "character AI chat",
      "R18 chat",
      "adult AI chat",
      "AI girlfriend chat",
      "AI boyfriend chat",
      "roleplay AI chat",
      "chatbot character",
      "chat to novel",
      "AI story from chat",
    ],
  },
  "/ai_chat/lp": {
    title: "AIチャット・R18チャット",
    description:
      "LexisのAIチャット紹介ページです。R18設定対応のAIチャットや、会話からAI小説化する機能を確認できます。",
    keywords: [
      "AIチャット",
      "R18チャット",
      "18禁チャット",
      "AI小説化",
      "会話から小説生成",
    ],
  },
  "/ai_chat/howto": {
    title: "AIチャットの使い方",
    description: "LexisのAIチャット機能の使い方を確認できます。",
  },
  "/ai_chat/public": {
    title: "公開AIチャット",
    description: "公開されているAIチャットキャラクターを探せるページです。",
  },
};
const NOINDEX_PREFIXES = ["/admin", "/mypage", "/me", "/notifications", "/dms"];
const NOINDEX_PATHS = new Set([
  "/login",
  "/register",
  "/reset-password",
  "/oauth/callback",
  "/stripe/success",
  "/stripe/cancel",
  "/support/success",
  "/support/cancel",
  "/membership/success",
  "/membership/cancel",
]);

type HeaderList = Awaited<ReturnType<typeof headers>>;
type RouteParams = { path?: string[] };
type RouteSearchParams = Record<string, string | string[] | undefined>;
type RouteProps = { params: Promise<RouteParams>; searchParams?: Promise<RouteSearchParams> };
type SeoData = {
  title: string;
  description: string;
  canonical?: string;
  ogType?: "website" | "book" | "article" | "profile";
  keywords?: string[];
  imageUrl?: string;
  languageAlternates?: Record<string, string>;
};
type BuildMetadataParams = {
  title: string;
  description: string;
  absoluteTitle?: string;
  canonical?: string;
  ogType?: "website" | "book" | "article" | "profile";
  noIndex?: boolean;
  keywords?: string[];
  imageUrl?: string;
  languageAlternates?: Record<string, string>;
};

function decodeHtml(value: unknown) {
  return String(value || "")
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'");
}

function compactText(value: unknown, maxLength = 140) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}

function getHeaderHost(headerList: HeaderList) {
  return (
    headerList.get("x-forwarded-host") ||
    headerList.get("host") ||
    "shosetsu-toukou-site.org"
  );
}

function getOrigin(headerList: HeaderList) {
  const proto = headerList.get("x-forwarded-proto") || "https";
  return `${proto}://${getHeaderHost(headerList)}`;
}

function resolveSeoLang(headerList: HeaderList): SeoLang {
  const raw = String(headerList.get("accept-language") || "").toLowerCase();
  if (raw.includes("zh-cn") || raw.includes("zh-hans")) return "zh-cn";
  if (raw.includes("zh-tw") || raw.includes("zh-hant") || raw.includes("zh-hk")) return "zh-tw";
  if (raw.includes("ko")) return "ko";
  if (raw.includes("en")) return "en";
  return "ja";
}

function resolveLocalizedText(value: LocalizedText, lang: SeoLang): string {
  if (typeof value === "string") return value;
  return value[lang] || value.en || value.ja || "";
}

function resolveLocalizedKeywords(value: LocalizedKeywords | undefined, lang: SeoLang): string[] | undefined {
  if (!value) return undefined;
  if (Array.isArray(value)) return value;
  return value[lang] || value.en || value.ja;
}

function pathFromParams(params?: RouteParams) {
  return Array.isArray(params?.path) ? params.path.map(String) : [];
}

function routePath(pathParts: string[]) {
  const path = `/${pathParts.map((part) => encodeURIComponent(part)).join("/")}`;
  return path === "/" ? "/" : path.replace(/\/$/, "");
}

function isNovelDetailPath(pathParts: string[]) {
  return pathParts.length === 2 && pathParts[0] === "novels" && /^\d+$/.test(pathParts[1]);
}

function isEpisodeDetailPath(pathParts: string[]) {
  return pathParts.length === 2 && pathParts[0] === "episodes" && /^\d+$/.test(pathParts[1]);
}

function isTagIndexPath(pathParts: string[]) {
  return pathParts.length === 1 && pathParts[0] === "tags";
}

function isTagDetailPath(pathParts: string[]) {
  return pathParts.length === 2 && pathParts[0] === "tags" && !!pathParts[1];
}

function isSeoPagePath(pathParts: string[]) {
  return pathParts.length === 2 && pathParts[0] === "seo" && !!pathParts[1];
}

function parseMetaContent(html: string, selectorName: string) {
  const escaped = selectorName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const patterns = [
    new RegExp(`<meta\\s+[^>]*(?:name|property)=["']${escaped}["'][^>]*content=["']([^"']*)["'][^>]*>`, "i"),
    new RegExp(`<meta\\s+[^>]*content=["']([^"']*)["'][^>]*(?:name|property)=["']${escaped}["'][^>]*>`, "i"),
  ];
  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match?.[1]) return decodeHtml(match[1]);
  }
  return "";
}

async function fetchFromBackend(
  path: string,
  headerList: HeaderList,
  options: RequestInit & { next?: { revalidate?: number } } = {}
) {
  const res = await fetch(`${BACKEND_ORIGIN}${path}`, {
    ...options,
    headers: {
      "x-forwarded-host": getHeaderHost(headerList),
      "x-forwarded-proto": headerList.get("x-forwarded-proto") || "https",
      ...(options.headers || {}),
    },
    next: { revalidate: 300, ...(options.next || {}) },
  });
  if (!res.ok) return null;
  return res;
}

async function fetchBackendJson<T = any>(path: string, headerList: HeaderList): Promise<T | null> {
  const res = await fetchFromBackend(path, headerList);
  if (!res) return null;
  return res.json().catch(() => null);
}

async function getNovelSeo(id: string, headerList: HeaderList): Promise<SeoData | null> {
  const res = await fetchFromBackend(`/prerender/novels/${id}`, headerList);
  if (!res) return null;
  const html = await res.text();
  const title = decodeHtml(html.match(/<title>([^<]*)<\/title>/i)?.[1] || "");
  const description = parseMetaContent(html, "description");
  const canonical =
    html.match(/<link\s+[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["'][^>]*>/i)?.[1] ||
    "";
  return {
    title: title.replace(/｜小説投稿サイトLexis.*$/, "") || "小説詳細",
    description: compactText(description || DEFAULT_DESCRIPTION),
    canonical: decodeHtml(canonical),
    ogType: "book" as const,
    imageUrl: parseMetaContent(html, "og:image") || `${getOrigin(headerList)}/ogp/novel/${id}.png`,
  };
}

async function getEpisodeSeo(id: string, headerList: Headers) {
  const res = await fetchFromBackend(`/prerender/episodes/${id}`, headerList);
  if (!res) return null;
  const html = await res.text();
  const title = decodeHtml(html.match(/<title>([^<]*)<\/title>/i)?.[1] || "");
  const description = parseMetaContent(html, "description");
  const canonical =
    html.match(/<link\s+[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["'][^>]*>/i)?.[1] ||
    "";
  return {
    title: title.replace(/｜小説投稿サイトLexis.*$/, "") || "エピソード詳細",
    description: compactText(description || DEFAULT_DESCRIPTION),
    canonical: decodeHtml(canonical),
    ogType: "article" as const,
  };
}

function getFirstSearchParam(searchParams: RouteSearchParams | undefined, key: string) {
  const value = searchParams?.[key];
  return Array.isArray(value) ? String(value[0] || "") : String(value || "");
}

function stripSiteTitleSuffix(value: unknown) {
  return String(value || "").replace(/｜小説投稿サイトLexis.*$/, "").trim();
}

async function getTagSeo(tagName: string, headerList: HeaderList, options: { r18View?: boolean } = {}): Promise<SeoData | null> {
  const encoded = encodeURIComponent(tagName);
  const r18View = options.r18View === true;
  const novelsQuery = r18View ? "sort=popular&limit=6&age_limit=r18" : "sort=popular&limit=6";
  const [detailRes, novelsRes] = await Promise.all([
    fetchFromBackend(`/api/tags/${encoded}`, headerList),
    fetchFromBackend(`/api/tags/${encoded}/novels?${novelsQuery}`, headerList),
  ]);
  if (!detailRes) return null;
  const detail = await detailRes.json().catch(() => ({}));
  const novels = novelsRes ? await novelsRes.json().catch(() => []) : [];
  const count = Number(detail?.novel_count || 0);
  const examples = Array.isArray(novels)
    ? novels
        .map((novel) => String(novel?.title || "").trim())
        .filter(Boolean)
        .slice(0, 3)
    : [];
  const suffix = examples.length ? `代表作: ${examples.join("、")}。` : "";
  if (r18View) {
    const apiKeywords: string[] = Array.isArray(detail?.seo_r18_keywords)
      ? detail.seo_r18_keywords.map((value: unknown) => String(value || "").trim()).filter(Boolean)
      : [];
    return {
      title: stripSiteTitleSuffix(detail?.seo_r18_title || `${tagName}のエロ小説・R18小説一覧`),
      description: compactText(
        String(detail?.seo_r18_description || `「${tagName}」タグのR18小説・エロ小説一覧です。${tagName}の成人向け作品を人気順・新着順で探せます。${suffix}`),
        160
      ),
      keywords: apiKeywords.length
        ? apiKeywords
        : [tagName, `${tagName} エロ小説`, `エロ小説 ${tagName}`, `${tagName} R18小説`, `R18小説 ${tagName}`, "エロ小説", "R18小説", "成人向け小説"],
    };
  }
  const apiKeywords: string[] = Array.isArray(detail?.seo_keywords)
    ? detail.seo_keywords.map((value: unknown) => String(value || "").trim()).filter(Boolean)
    : [];
  return {
    title: stripSiteTitleSuffix(detail?.seo_title || `${tagName}小説一覧`),
    description: compactText(
      String(detail?.seo_description || `「${tagName}」タグの小説一覧です。${count ? `${count}件の作品を掲載中。` : ""}人気順・新着順で作品を探せます。${suffix}`),
      160
    ),
    keywords: apiKeywords.length
      ? apiKeywords
      : [tagName, `${tagName} 小説`, `${tagName} タグ`, "小説", "Web小説"],
  };
}

async function getSeoPageSeo(slug: string, headerList: HeaderList): Promise<SeoData | null> {
  const data = await fetchBackendJson<any>(`/api/seo-pages/${encodeURIComponent(slug)}`, headerList);
  if (!data) return null;
  return {
    title: String(data?.title || data?.h1 || "SEOページ"),
    description: compactText(data?.description || data?.body || DEFAULT_DESCRIPTION, 160),
    canonical: `${getOrigin(headerList)}${String(data?.canonical_path || `/seo/${slug}`)}`,
    ogType: "website",
  };
}

function buildMetadata({
  title,
  description,
  absoluteTitle,
  canonical,
  ogType = "website",
  noIndex = false,
  keywords,
  imageUrl,
  languageAlternates,
}: BuildMetadataParams): Metadata {
  const resolvedTitle = absoluteTitle || title;
  const resolvedImageUrl = imageUrl || "/ogp.png";
  return {
    title: absoluteTitle ? { absolute: absoluteTitle } : title,
    description,
    keywords,
    alternates: canonical || languageAlternates ? { canonical, languages: languageAlternates } : undefined,
    robots: {
      index: !noIndex,
      follow: !noIndex,
    },
    openGraph: {
      title: resolvedTitle,
      description,
      type: ogType,
      url: canonical,
      siteName: SITE_NAME,
      images: [{ url: resolvedImageUrl, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: resolvedTitle,
      description,
      images: [resolvedImageUrl],
    },
  };
}

export async function generateMetadata({ params, searchParams }: RouteProps): Promise<Metadata> {
  const resolvedParams = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const pathParts = pathFromParams(resolvedParams);
  const headerList = await headers();
  const seoLang = resolveSeoLang(headerList);
  const origin = getOrigin(headerList);
  const canonical = `${origin}${routePath(pathParts)}`;

  if (pathParts.length === 0) {
    return buildMetadata({
      title: "小説投稿サイトLexis（レクシー/レクシス）",
      description: DEFAULT_DESCRIPTION,
      canonical: `${origin}/`,
    });
  }

  if (isNovelDetailPath(pathParts)) {
    const seo = await getNovelSeo(pathParts[1], headerList);
    if (!seo) {
      return buildMetadata({
        title: "小説が見つかりません",
        description: "指定された小説は見つかりませんでした。",
        canonical,
        noIndex: true,
      });
    }
    return buildMetadata({
      title: seo.title,
      description: seo.description,
      canonical: seo.canonical || canonical,
      ogType: seo.ogType,
      imageUrl: seo.imageUrl,
    });
  }

  if (isEpisodeDetailPath(pathParts)) {
    const seo = await getEpisodeSeo(pathParts[1], headerList);
    if (!seo) {
      return buildMetadata({
        title: "エピソードが見つかりません",
        description: "指定されたエピソードは見つかりませんでした。",
        canonical,
        noIndex: true,
      });
    }
    return buildMetadata({
      title: seo.title,
      description: seo.description,
      canonical: seo.canonical || canonical,
      ogType: seo.ogType,
    });
  }

  if (isTagIndexPath(pathParts)) {
    return buildMetadata({
      title: "タグ一覧",
      description: "人気タグから小説を探せます。タグ経由で新しい作品と作者に出会えます。",
      canonical,
      keywords: ["タグ一覧", "小説タグ", "r18", "エロ"],
    });
  }

  if (isTagDetailPath(pathParts)) {
    const tagName = decodeURIComponent(pathParts[1]);
    const isR18TagView = getFirstSearchParam(resolvedSearchParams, "age_limit").toLowerCase() === "r18";
    const seo = await getTagSeo(tagName, headerList, { r18View: isR18TagView });
    if (!seo) {
      return buildMetadata({
        title: "タグが見つかりません",
        description: "指定されたタグは見つかりませんでした。",
        canonical,
        noIndex: true,
      });
    }
    return buildMetadata({
      title: seo.title,
      description: seo.description,
      canonical: isR18TagView ? `${canonical}?age_limit=r18` : canonical,
      keywords: seo.keywords,
    });
  }

  if (isSeoPagePath(pathParts)) {
    const slug = decodeURIComponent(pathParts[1]);
    const seo = await getSeoPageSeo(slug, headerList);
    if (!seo) {
      return buildMetadata({
        title: "ページが見つかりません",
        description: "指定されたページは見つかりませんでした。",
        canonical,
        noIndex: true,
      });
    }
    return buildMetadata({
      title: seo.title,
      description: seo.description,
      canonical: seo.canonical || canonical,
      ogType: "website",
    });
  }

  if (pathParts.length === 2 && pathParts[0] === "series") {
    const seriesName = decodeURIComponent(pathParts[1]);
    return buildMetadata({
      title: `${seriesName}シリーズ`,
      description: `「${seriesName}」シリーズの小説一覧です。関連作品をまとめて探せます。`,
      canonical,
    });
  }

  if (pathParts.length === 2 && pathParts[0] === "users") {
    const username = decodeURIComponent(pathParts[1]);
    return buildMetadata({
      title: `${username}の小説`,
      description: `${username}さんの公開小説とプロフィールを確認できます。`,
      canonical,
      ogType: "profile",
    });
  }

  const staticSeo = STATIC_PAGE_SEO[routePath(pathParts)];
  if (staticSeo) {
    return buildMetadata({
      title: resolveLocalizedText(staticSeo.title, routePath(pathParts) === "/en/ai-novel" || routePath(pathParts) === "/en/ai_chat" ? "en" : routePath(pathParts) === "/ai-novel" || routePath(pathParts) === "/ai_chat" ? "ja" : seoLang),
      description: resolveLocalizedText(staticSeo.description, routePath(pathParts) === "/en/ai-novel" || routePath(pathParts) === "/en/ai_chat" ? "en" : routePath(pathParts) === "/ai-novel" || routePath(pathParts) === "/ai_chat" ? "ja" : seoLang),
      absoluteTitle: staticSeo.absoluteTitle
        ? resolveLocalizedText(staticSeo.absoluteTitle, routePath(pathParts) === "/en/ai-novel" || routePath(pathParts) === "/en/ai_chat" ? "en" : routePath(pathParts) === "/ai-novel" || routePath(pathParts) === "/ai_chat" ? "ja" : seoLang)
        : undefined,
      canonical,
      ogType: staticSeo.ogType || "website",
      keywords: resolveLocalizedKeywords(staticSeo.keywords, routePath(pathParts) === "/en/ai-novel" || routePath(pathParts) === "/en/ai_chat" ? "en" : routePath(pathParts) === "/ai-novel" || routePath(pathParts) === "/ai_chat" ? "ja" : seoLang),
      languageAlternates:
        routePath(pathParts) === "/ai-novel" || routePath(pathParts) === "/en/ai-novel"
          ? { ja: `${origin}/ai-novel`, en: `${origin}/en/ai-novel`, "x-default": `${origin}/ai-novel` }
          : routePath(pathParts) === "/ai_chat" || routePath(pathParts) === "/en/ai_chat"
          ? { ja: `${origin}/ai_chat`, en: `${origin}/en/ai_chat`, "x-default": `${origin}/ai_chat` }
          : undefined,
    });
  }

  const shouldNoIndex =
    NOINDEX_PATHS.has(routePath(pathParts)) ||
    NOINDEX_PREFIXES.some((prefix) => routePath(pathParts) === prefix || routePath(pathParts).startsWith(`${prefix}/`));
  if (shouldNoIndex) {
    return buildMetadata({
      title: SITE_NAME,
      description: DEFAULT_DESCRIPTION,
      canonical,
      noIndex: true,
    });
  }

  return buildMetadata({
    title: SITE_NAME,
    description: DEFAULT_DESCRIPTION,
    canonical,
  });
}

function JsonLd({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return null;
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}

async function buildJsonLd(pathParts: string[], searchParams?: RouteSearchParams): Promise<Record<string, unknown> | null> {
  const headerList = await headers();
  const origin = getOrigin(headerList);
  if (pathParts.length === 0) {
    return {
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: SITE_NAME,
      url: `${origin}/`,
      potentialAction: {
        "@type": "SearchAction",
        target: `${origin}/?q={search_term_string}`,
        "query-input": "required name=search_term_string",
      },
    };
  }

  if (isTagIndexPath(pathParts)) {
    return {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      name: "タグ一覧",
      url: `${origin}/tags`,
      description: "人気タグから小説を探せます。",
    };
  }

  if (isTagDetailPath(pathParts)) {
    const tagName = decodeURIComponent(pathParts[1]);
    const isR18TagView = getFirstSearchParam(searchParams, "age_limit").toLowerCase() === "r18";
    return {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      name: isR18TagView ? `${tagName}のエロ小説・R18小説一覧` : `${tagName}小説一覧`,
      url: `${origin}/tags/${encodeURIComponent(tagName)}${isR18TagView ? "?age_limit=r18" : ""}`,
      about: isR18TagView ? [tagName, `${tagName} エロ小説`, `エロ小説 ${tagName}`, `${tagName} R18小説`] : tagName,
      keywords: isR18TagView ? `${tagName}, ${tagName} エロ小説, エロ小説 ${tagName}, ${tagName} R18小説, R18小説 ${tagName}` : `${tagName}, ${tagName} 小説`,
    };
  }

  if (isSeoPagePath(pathParts)) {
    const slug = decodeURIComponent(pathParts[1]);
    const page = await fetchBackendJson<any>(`/api/seo-pages/${encodeURIComponent(slug)}`, headerList);
    if (!page) return null;
    const canonical = `${origin}${String(page?.canonical_path || `/seo/${slug}`)}`;
    return {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebPage",
          name: String(page?.title || page?.h1 || "SEOページ"),
          description: compactText(page?.description || page?.body || "", 200),
          url: canonical,
          keywords: Array.isArray(page?.related_tags) ? page.related_tags.join(", ") : "",
        },
        {
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Home", item: `${origin}/` },
            { "@type": "ListItem", position: 2, name: String(page?.h1 || page?.title || "SEOページ"), item: canonical },
          ],
        },
      ],
    };
  }

  if (isNovelDetailPath(pathParts)) {
    const novelId = pathParts[1];
    const novel = await fetchBackendJson<any>(`/api/novels/${novelId}`, headerList);
    if (!novel) return null;
    const canonical = `${origin}/novels/${novelId}`;
    const authorName = String(novel?.author_username || "").trim();
    const tags = Array.isArray(novel?.tags)
      ? novel.tags.map((tag: any) => String(tag?.name || "").trim()).filter(Boolean)
      : [];
    const description = compactText(novel?.description || "", 200);
    return {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Book",
          name: String(novel?.title || "小説詳細"),
          description,
          url: canonical,
          inLanguage: String(novel?.language || "ja"),
          keywords: tags.join(", "),
          author: authorName ? { "@type": "Person", name: authorName, url: `${origin}/users/${encodeURIComponent(authorName)}` } : undefined,
        },
        {
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Home", item: `${origin}/` },
            { "@type": "ListItem", position: 2, name: String(novel?.title || "小説詳細"), item: canonical },
          ],
        },
      ],
    };
  }

  if (isEpisodeDetailPath(pathParts)) {
    const episodeId = pathParts[1];
    const episode = await fetchBackendJson<any>(`/api/episodes/${episodeId}`, headerList);
    if (!episode) return null;
    const canonical = `${origin}/episodes/${episodeId}`;
    const novelId = String(episode?.novel_id || "");
    const novelTitle = String(episode?.novel_title || "作品");
    const authorName = String(episode?.author_username || "").trim();
    const tagSource = Array.isArray(episode?.tags) ? episode.tags : Array.isArray(episode?.novel_tags) ? episode.novel_tags : [];
    const tags = tagSource.map((tag: any) => String(tag?.name || "").trim()).filter(Boolean);
    const description = compactText(episode?.body || episode?.novel_description || "", 200);
    return {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Article",
          headline: String(episode?.title || "エピソード詳細"),
          description,
          articleBody: compactText(episode?.body || "", 3000),
          url: canonical,
          mainEntityOfPage: canonical,
          inLanguage: String(episode?.language || "ja"),
          keywords: tags.join(", "),
          author: authorName ? { "@type": "Person", name: authorName, url: `${origin}/users/${encodeURIComponent(authorName)}` } : undefined,
          isPartOf: novelId ? { "@type": "Book", name: novelTitle, url: `${origin}/novels/${novelId}` } : undefined,
          datePublished: episode?.created_at || undefined,
        },
        {
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Home", item: `${origin}/` },
            ...(novelId ? [{ "@type": "ListItem", position: 2, name: novelTitle, item: `${origin}/novels/${novelId}` }] : []),
            {
              "@type": "ListItem",
              position: novelId ? 3 : 2,
              name: String(episode?.title || "エピソード詳細"),
              item: canonical,
            },
          ],
        },
      ],
    };
  }

  if (
    (pathParts.length === 1 && pathParts[0] === "ai-novel") ||
    (pathParts.length === 2 && pathParts[0] === "en" && pathParts[1] === "ai-novel")
  ) {
    const isEnglishAiNovelPage = pathParts[0] === "en";
    return {
      "@context": "https://schema.org",
      "@type": "WebPage",
      inLanguage: isEnglishAiNovelPage ? "en" : "ja",
      name: isEnglishAiNovelPage
        ? "AI novel generator, story writing AI, and R18 draft support"
        : "AI小説生成・小説生成AI・R18小説生成",
      alternateName: isEnglishAiNovelPage
        ? "AI小説生成・小説生成AI・R18小説生成"
        : "AI novel generator, story writing AI, and R18 draft support",
      url: isEnglishAiNovelPage ? `${origin}/en/ai-novel` : `${origin}/ai-novel`,
      description: isEnglishAiNovelPage
        ? "Use Lexis as an AI novel generator and story writing AI. Create plots, characters, genres, prose, episode continuations, and R18 or adult novel drafts with editing support."
        : "LexisのAI小説生成ページです。小説生成AIでプロット、登場人物、ジャンル、文体を指定し、物語作成、R18小説生成、官能小説の下書き、続き生成、執筆支援に使えます。",
      keywords: (isEnglishAiNovelPage
        ? [
            "AI novel generator",
            "AI novel generation",
            "AI story generator",
            "story writing AI",
            "novel writing AI",
            "AI fiction writer",
            "adult novel AI",
            "R18 novel generation",
            "episode continuation generator",
            "writing assistant",
          ]
        : [
            "AI小説生成",
            "小説生成AI",
            "AI小説メーカー",
            "AI小説作成",
            "R18小説生成",
            "官能小説生成",
            "プロット生成",
            "続き生成",
            "執筆支援",
          ]).join(", "),
      about: isEnglishAiNovelPage
        ? ["AI novel generator", "AI story generator", "story writing AI", "R18 novel generation"]
        : ["AI小説生成", "小説生成AI", "R18小説生成", "官能小説生成"],
    };
  }

  if (
    (pathParts.length === 1 && pathParts[0] === "ai_chat") ||
    (pathParts.length === 2 && pathParts[0] === "en" && pathParts[1] === "ai_chat")
  ) {
    const isEnglishAiChatPage = pathParts[0] === "en";
    return {
      "@context": "https://schema.org",
      "@type": "WebPage",
      inLanguage: isEnglishAiChatPage ? "en" : "ja",
      name: isEnglishAiChatPage
        ? "AI chat, character AI chat, and R18 chat"
        : "AIチャット・キャラクターAIチャット・R18チャット",
      alternateName: isEnglishAiChatPage
        ? "AIチャット・キャラクターAIチャット・R18チャット"
        : "AI chat, character AI chat, and R18 chat",
      url: isEnglishAiChatPage ? `${origin}/en/ai_chat` : `${origin}/ai_chat`,
      description: isEnglishAiChatPage
        ? "Use Lexis for AI chat with custom characters, personality settings, relationships, R18 chat options, girlfriend or boyfriend roleplay, and chat-to-novel writing support."
        : "LexisのAIチャットページです。キャラクター設定、性格、関係性を作成して会話できます。R18チャット、恋人AIチャット、会話ログからAI小説化する機能にも対応しています。",
      keywords: (isEnglishAiChatPage
        ? [
            "AI chat",
            "character AI chat",
            "R18 chat",
            "adult AI chat",
            "AI girlfriend chat",
            "AI boyfriend chat",
            "roleplay AI chat",
            "chat to novel",
          ]
        : [
            "AIチャット",
            "キャラクターAIチャット",
            "R18チャット",
            "18禁チャット",
            "恋人AIチャット",
            "AI彼女",
            "AI彼氏",
            "AI小説化",
          ]).join(", "),
      about: isEnglishAiChatPage
        ? ["AI chat", "character AI chat", "R18 chat", "chat to novel"]
        : ["AIチャット", "キャラクターAIチャット", "R18チャット", "AI小説化"],
    };
  }

  if (pathParts.length === 2 && pathParts[0] === "ai_chat" && pathParts[1] === "lp") {
    return {
      "@context": "https://schema.org",
      "@type": "WebPage",
      name: "AIチャット・R18チャット",
      url: `${origin}/ai_chat/lp`,
      description:
        "R18設定対応のAIチャットと、会話ログからAI小説化できる機能を紹介するページです。",
      keywords: ["AIチャット", "R18チャット", "18禁チャット", "AI小説化"].join(", "),
      about: ["AIチャット", "R18チャット", "AI小説化"],
    };
  }

  return null;
}

export default async function Page({ params, searchParams }: RouteProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const pathParts = pathFromParams(resolvedParams);
  const jsonLd = await buildJsonLd(pathParts, resolvedSearchParams);
  return (
    <>
      <JsonLd data={jsonLd} />
      <ClientApp />
    </>
  );
}
