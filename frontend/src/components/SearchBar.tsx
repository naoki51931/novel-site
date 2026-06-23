import { useEffect, useMemo, useState } from "react";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { getErrorMessage } from "../lib/errorUtils";

const API_BASE = getApiBase();

type TranslateFn = (messages: Record<string, string>, vars?: Record<string, string | number>) => string;
type TokenKind = "mixed" | "user" | "tag";

type ActiveTokenContext = {
  start: number;
  token: string;
  kind: TokenKind;
  keyword: string;
};

type Suggestion = {
  key: string;
  kind: Exclude<TokenKind, "mixed">;
  label: string;
  value: string;
  count: number;
};

type SearchBarProps = {
  query: string;
  excludeQuery: string;
  sort?: string;
  ageLimit?: string;
  creativeType?: string;
  onChangeQuery: (value: string) => void;
  onChangeExcludeQuery: (value: string) => void;
  onChangeSort?: (value: string) => void;
  onChangeAgeLimit?: (value: string) => void;
  onChangeCreativeType?: (value: string) => void;
  onSearch?: (params: {
    query: string;
    excludeQuery: string;
    sort: string;
    ageLimit: string;
    creativeType: string;
    directTagName?: string;
  }) => void;
};

type SearchUserResult = {
  user_id?: number | string | null;
  username?: string | null;
  novel_count?: number | null;
};

type SearchTagResult = {
  tag_id?: number | string | null;
  name?: string | null;
  novel_count?: number | null;
};

type SearchResponse =
  | { type: "user"; ok: boolean; data: SearchUserResult[] }
  | { type: "tag"; ok: boolean; data: SearchTagResult[] };

function findActiveTokenContext(value: unknown): ActiveTokenContext | null {
  const text = String(value || "");
  if (!text) return null;
  const last = text.charAt(text.length - 1);
  if (last === " " || last === ",") return null;

  let start = text.length - 1;
  while (start > 0) {
    const ch = text.charAt(start - 1);
    if (ch === " " || ch === ",") break;
    start -= 1;
  }

  const token = text.slice(start);
  if (!token) return null;

  let kind: TokenKind = "mixed";
  let keyword = token;
  if (token.startsWith("@")) {
    kind = "user";
    keyword = token.slice(1);
  } else if (token.startsWith("#")) {
    kind = "tag";
    keyword = token.slice(1);
  }
  keyword = keyword.trim();
  if (!keyword) return null;
  return { start, token, kind, keyword };
}

function replaceActiveToken(value: unknown, context: ActiveTokenContext | null, replacement: string) {
  if (!context) return String(value || "");
  const head = String(value || "").slice(0, context.start);
  return `${head}${replacement} `;
}

export default function SearchBar({
  query,
  excludeQuery,
  sort = "new",
  ageLimit = "",
  creativeType = "",
  onChangeQuery,
  onChangeExcludeQuery,
  onChangeSort,
  onChangeAgeLimit,
  onChangeCreativeType,
  onSearch,
}: SearchBarProps) {
  const { t } = useI18n();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestError, setSuggestError] = useState("");
  const [activeSuggestIndex, setActiveSuggestIndex] = useState(-1);
  const activeToken = useMemo(() => findActiveTokenContext(query), [query]);

  useEffect(() => {
    if (!activeToken?.keyword) {
      setSuggestions([]);
      setSuggestLoading(false);
      setSuggestError("");
      setActiveSuggestIndex(-1);
      return;
    }
    let canceled = false;
    const timer = setTimeout(async () => {
      try {
        setSuggestLoading(true);
        setSuggestError("");
        const keyword = activeToken.keyword;
        const kind = activeToken.kind;
        const requests: Array<Promise<SearchResponse>> = [];
        if (kind === "user") {
          requests.push(
            fetch(`${API_BASE}/api/search/users?q=${encodeURIComponent(keyword)}&limit=8`, {
              cache: "no-store",
            }).then(async (res) => ({
              type: "user",
              ok: res.ok,
              data: await res.json().catch(() => []),
            }))
          );
        } else if (kind === "tag") {
          requests.push(
            fetch(`${API_BASE}/api/search/tags?q=${encodeURIComponent(keyword)}&limit=8`, {
              cache: "no-store",
            }).then(async (res) => ({
              type: "tag",
              ok: res.ok,
              data: await res.json().catch(() => []),
            }))
          );
        } else {
          requests.push(
            fetch(`${API_BASE}/api/search/tags?q=${encodeURIComponent(keyword)}&limit=6`, {
              cache: "no-store",
            }).then(async (res) => ({
              type: "tag",
              ok: res.ok,
              data: await res.json().catch(() => []),
            }))
          );
          requests.push(
            fetch(`${API_BASE}/api/search/users?q=${encodeURIComponent(keyword)}&limit=4`, {
              cache: "no-store",
            }).then(async (res) => ({
              type: "user",
              ok: res.ok,
              data: await res.json().catch(() => []),
            }))
          );
        }

        const results = await Promise.all(requests);
        const failed = results.find((r) => !r.ok);
        if (failed) {
          throw new Error(
            t({ ja: "検索候補の取得に失敗しました。", en: "Failed to load search suggestions." })
          );
        }
        if (canceled) return;

        const merged: Suggestion[] = [];
        for (const result of results) {
          if (result.type === "user") {
            for (const item of Array.isArray(result.data) ? result.data : []) {
              const username = String(item?.username || "").trim();
              if (!username) continue;
              merged.push({
                key: `user-${item?.user_id || username}`,
                kind: "user",
                label: `@${username}`,
                value: `@${username}`,
                count: Number(item?.novel_count || 0),
              });
            }
          } else {
            for (const item of Array.isArray(result.data) ? result.data : []) {
              const name = String(item?.name || "").trim();
              if (!name) continue;
              merged.push({
                key: `tag-${item?.tag_id || name}`,
                kind: "tag",
                label: `#${name}`,
                value: name,
                count: Number(item?.novel_count || 0),
              });
            }
          }
        }
        setSuggestions(merged.slice(0, 10));
        setActiveSuggestIndex(-1);
      } catch (e) {
        if (canceled) return;
        setSuggestions([]);
        setSuggestError(
          getErrorMessage(
            e,
            t({ ja: "検索候補の取得に失敗しました。", en: "Failed to load search suggestions." })
          )
        );
      } finally {
        if (!canceled) setSuggestLoading(false);
      }
    }, 180);

    return () => {
      canceled = true;
      clearTimeout(timer);
    };
  }, [activeToken, t]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (onSearch) {
      onSearch({ query, excludeQuery, sort, ageLimit, creativeType });
    }
  };

  const handlePickSuggestion = (item: Suggestion, { submit = false }: { submit?: boolean } = {}) => {
    if (!onChangeQuery || !activeToken) return;
    const next = replaceActiveToken(query, activeToken, item.value);
    onChangeQuery(next);
    setSuggestions([]);
    setSuggestError("");
    setActiveSuggestIndex(-1);
    if (submit && onSearch) {
      onSearch({
        query: item.kind === "tag" ? item.value : next,
        directTagName: item.kind === "tag" ? item.value : undefined,
        excludeQuery,
        sort,
        ageLimit,
        creativeType,
      });
    }
  };

  const handleKeyDownQuery = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!activeToken?.keyword || suggestions.length === 0) {
      if (e.key === "Escape") {
        setSuggestions([]);
        setSuggestError("");
        setActiveSuggestIndex(-1);
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSuggestIndex((prev) => {
        const next = prev + 1;
        return next >= suggestions.length ? 0 : next;
      });
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSuggestIndex((prev) => {
        if (prev <= 0) return suggestions.length - 1;
        return prev - 1;
      });
      return;
    }
    if (e.key === "Enter" && activeSuggestIndex >= 0) {
      e.preventDefault();
      handlePickSuggestion(suggestions[activeSuggestIndex], { submit: !!e.shiftKey });
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      setSuggestions([]);
      setSuggestError("");
      setActiveSuggestIndex(-1);
    }
  };

  return (
    <form className={`search-bar ${activeToken?.keyword ? "search-bar-suggest-open" : ""}`.trim()} onSubmit={handleSubmit}>
      <div className="search-query-wrap">
        <input
          name="query"
          type="text"
          placeholder={t({
            ja: "検索: タイトル/本文/概要/タグ(空白・カンマ)/@ユーザー",
            en: "Search: title/body/summary/tags (space/comma)/@user",
          })}
          value={query}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChangeQuery(e.target.value)}
          onKeyDown={handleKeyDownQuery}
          className="search-input"
        />
        {activeToken?.keyword ? (
          <div className="search-suggest-panel">
            {suggestLoading ? (
              <div className="search-suggest-item">
                {t({ ja: "検索候補を取得中...", en: "Loading suggestions..." })}
              </div>
            ) : suggestError ? (
              <div className="search-suggest-item search-suggest-error">{suggestError}</div>
            ) : suggestions.length === 0 ? (
              <div className="search-suggest-item">
                {t({ ja: "一致する候補がありません。", en: "No matching suggestions." })}
              </div>
            ) : (
              suggestions.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`search-suggest-item search-suggest-button ${
                    suggestions[activeSuggestIndex]?.key === item.key ? "search-suggest-active" : ""
                  }`}
                  onMouseEnter={() => {
                    const idx = suggestions.findIndex((s) => s.key === item.key);
                    if (idx >= 0) setActiveSuggestIndex(idx);
                  }}
                  onMouseDown={(e: React.MouseEvent<HTMLButtonElement>) => {
                    e.preventDefault();
                    handlePickSuggestion(item, { submit: item.kind === "tag" });
                  }}
                >
                  <span>{item.label}</span>
                  <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                    <span className="search-suggest-kind">
                      {item.kind === "tag"
                        ? t({ ja: "タグ", en: "Tag" })
                        : t({ ja: "作者", en: "Author" })}
                    </span>
                    <span>
                      {t(
                        { ja: "{{count}} 作品", en: "{{count}} works" },
                        { count: Number(item.count || 0) }
                      )}
                    </span>
                  </span>
                </button>
              ))
            )}
          </div>
        ) : null}
      </div>
      <input
        name="exclude_query"
        type="text"
        placeholder={t({
          ja: "除外: タイトル/本文/概要/タグ(空白・カンマ)/@ユーザー",
          en: "Exclude: title/body/summary/tags (space/comma)/@user",
        })}
        value={excludeQuery}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChangeExcludeQuery(e.target.value)}
        className="search-input"
      />
      <select
        name="sort"
        value={sort}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onChangeSort && onChangeSort(e.target.value)}
        className="search-input"
        aria-label={t({ ja: "並び順", en: "Sort" })}
      >
        <option value="new">{t({ ja: "新着順", en: "Newest" })}</option>
        <option value="popular">{t({ ja: "人気順（プレミアム限定）", en: "Popular (Premium only)" })}</option>
        <option value="likes">{t({ ja: "いいね順（プレミアム限定）", en: "Likes (Premium only)" })}</option>
        <option value="comments">{t({ ja: "コメント順（プレミアム限定）", en: "Comments (Premium only)" })}</option>
      </select>
      <select
        name="age_limit"
        value={ageLimit}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onChangeAgeLimit && onChangeAgeLimit(e.target.value)}
        className="search-input"
        aria-label={t({ ja: "年齢区分", en: "Age limit" })}
      >
        <option value="">{t({ ja: "年齢区分: すべて", en: "Age: All" })}</option>
        <option value="all">all</option>
        <option value="r15">r15</option>
        <option value="r18">r18</option>
      </select>
      <select
        name="creative_type"
        value={creativeType}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onChangeCreativeType && onChangeCreativeType(e.target.value)}
        className="search-input"
        aria-label={t({ ja: "創作区分", en: "Creative type" })}
      >
        <option value="">{t({ ja: "創作区分: すべて", en: "Type: All" })}</option>
        <option value="original">original</option>
        <option value="fanfic">fanfic</option>
      </select>

      <button type="submit" className="search-button">
        {t({ ja: "検索", en: "Search" })}
      </button>
    </form>
  );
}
