import type { Metadata } from "next";
import { headers } from "next/headers";
import ClientApp from "../../NextClientApp";

export const dynamic = "force-dynamic";

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
    title: string;
    description: string;
    ogType?: "website" | "book" | "article" | "profile";
    keywords?: string[];
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
    title: "AI小説生成・R18小説生成",
    description:
      "AI小説生成ができるLexisのページです。R18小説生成、官能小説生成、物語の続き生成、執筆支援に対応しています。",
    keywords: [
      "AI小説",
      "AI小説生成",
      "小説生成AI",
      "R18小説生成",
      "官能小説生成",
      "AI 官能小説",
      "物語 生成",
      "執筆支援",
    ],
  },
  "/ai_chat": {
    title: "AIチャット",
    description: "キャラクターと会話できるAIチャットページです。",
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
type RouteProps = { params: Promise<RouteParams> };
type SeoData = { title: string; description: string; canonical?: string; ogType?: "website" | "book" | "article" | "profile" };
type BuildMetadataParams = {
  title: string;
  description: string;
  canonical?: string;
  ogType?: "website" | "book" | "article" | "profile";
  noIndex?: boolean;
  keywords?: string[];
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

async function getTagSeo(tagName: string, headerList: HeaderList): Promise<SeoData | null> {
  const encoded = encodeURIComponent(tagName);
  const [detailRes, novelsRes] = await Promise.all([
    fetchFromBackend(`/api/tags/${encoded}`, headerList),
    fetchFromBackend(`/api/tags/${encoded}/novels?sort=popular&limit=6`, headerList),
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
  return {
    title: `${tagName}小説一覧`,
    description: compactText(
      `「${tagName}」タグの小説一覧です。${count ? `${count}件の作品を掲載中。` : ""}人気順・新着順で作品を探せます。${suffix}`,
      160
    ),
  };
}

function buildMetadata({
  title,
  description,
  canonical,
  ogType = "website",
  noIndex = false,
  keywords,
}: BuildMetadataParams): Metadata {
  return {
    title,
    description,
    keywords,
    alternates: canonical ? { canonical } : undefined,
    robots: {
      index: !noIndex,
      follow: !noIndex,
    },
    openGraph: {
      title,
      description,
      type: ogType,
      url: canonical,
      siteName: SITE_NAME,
      images: [{ url: "/ogp.png", width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/ogp.png"],
    },
  };
}

export async function generateMetadata({ params }: RouteProps): Promise<Metadata> {
  const resolvedParams = await params;
  const pathParts = pathFromParams(resolvedParams);
  const headerList = await headers();
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
    });
  }

  if (isTagDetailPath(pathParts)) {
    const tagName = decodeURIComponent(pathParts[1]);
    const seo = await getTagSeo(tagName, headerList);
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
      canonical,
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
      title: staticSeo.title,
      description: staticSeo.description,
      canonical,
      ogType: staticSeo.ogType || "website",
      keywords: staticSeo.keywords,
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

async function buildJsonLd(pathParts: string[]): Promise<Record<string, unknown> | null> {
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
    return {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      name: `${tagName}小説一覧`,
      url: `${origin}/tags/${encodeURIComponent(tagName)}`,
      about: tagName,
    };
  }

  if (pathParts.length === 1 && pathParts[0] === "ai-novel") {
    return {
      "@context": "https://schema.org",
      "@type": "WebPage",
      name: "AI小説生成・R18小説生成",
      url: `${origin}/ai-novel`,
      description:
        "AI小説生成、R18小説生成、官能小説生成、続き生成、執筆支援ができるページです。",
      keywords: [
        "AI小説生成",
        "R18小説生成",
        "官能小説生成",
        "小説生成AI",
        "執筆支援",
      ].join(", "),
      about: ["AI小説生成", "R18小説生成", "官能小説生成"],
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

export default async function Page({ params }: RouteProps) {
  const resolvedParams = await params;
  const pathParts = pathFromParams(resolvedParams);
  const jsonLd = await buildJsonLd(pathParts);
  return (
    <>
      <JsonLd data={jsonLd} />
      <ClientApp />
    </>
  );
}
