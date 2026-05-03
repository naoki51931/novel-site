import { Link } from "react-router-dom";
import TagChipLink from "./TagChipLink";
import { hasRecentEpisodeActivity } from "../lib/freshness";

type TranslateFn = (messages: Record<string, string>, vars?: Record<string, string | number>) => string;

type TagLike = string | { name?: string | null } | null | undefined;

type NovelCardNovel = {
  id: number | string;
  title?: string | null;
  description?: string | null;
  cover_image_url?: string | null;
  tag_names?: Array<string | null | undefined> | null;
  tags?: TagLike[] | null;
  author_username?: string | null;
  age_limit?: string | null;
  creative_type?: string | null;
  like_count?: number | null;
  comment_count?: number | null;
  favorite_count?: number | null;
  view_count?: number | null;
  total_char_count?: number | null;
  created_at?: string | null;
  is_liked?: boolean | null;
  is_favorited?: boolean | null;
  latest_episode_activity_at?: string | null;
  latest_episode_created_at?: string | null;
};

type NovelCardProps = {
  novel: NovelCardNovel;
  t: TranslateFn;
  apiBase: string;
  maxTags?: number;
  descriptionMax?: number;
  showDescription?: boolean;
  showCreatedAt?: boolean;
  onLike?: ((novel: NovelCardNovel) => void) | null;
  onFavorite?: ((novel: NovelCardNovel) => void) | null;
  onTagClick?: ((name: string) => void) | null;
  footer?: React.ReactNode;
};

function resolveCoverUrl(apiBase: string, url: unknown) {
  if (!url) return "";
  return String(url).startsWith("http") ? String(url) : `${apiBase}${url}`;
}

function normalizeTagNames(novel: NovelCardNovel): string[] {
  if (Array.isArray(novel?.tag_names)) {
    return novel.tag_names.map((name) => String(name || "").trim()).filter(Boolean);
  }
  if (Array.isArray(novel?.tags)) {
    return novel.tags
      .map((item) =>
        typeof item === "string" ? item.trim() : String(item?.name ?? "").trim()
      )
      .filter(Boolean);
  }
  return [];
}

export default function NovelCard({
  novel,
  t,
  apiBase,
  maxTags = 4,
  descriptionMax = 120,
  showDescription = true,
  showCreatedAt = false,
  onLike = null,
  onFavorite = null,
  onTagClick = null,
  footer = null,
}: NovelCardProps) {
  const tagNames = normalizeTagNames(novel).slice(0, Math.max(0, Number(maxTags) || 0));
  const description = String(novel?.description || "").trim();
  const shortDescription =
    description.length > descriptionMax ? `${description.slice(0, descriptionMax)}...` : description;
  const coverUrl = resolveCoverUrl(apiBase, novel?.cover_image_url);
  const showFreshBadge = hasRecentEpisodeActivity(novel, 7);

  return (
    <article className="novel-card-ui">
      {coverUrl ? (
        <Link to={`/novels/${novel.id}`} className="novel-card-cover-link" aria-label={String(novel?.title || "")}>
          <img src={coverUrl} alt={t({ ja: "表紙画像", en: "Cover image" })} className="novel-card-cover" />
        </Link>
      ) : null}

      <div className="novel-card-body">
        <h3 className="novel-card-title">
          <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
        </h3>

        <div className="novel-card-author-row">
          <span>{t({ ja: "作者", en: "Author" })}: </span>
          {novel.author_username ? (
            <Link className="user-link" to={`/users/${encodeURIComponent(novel.author_username)}`}>
              @{novel.author_username}
            </Link>
          ) : (
            <span>{t({ ja: "不明", en: "Unknown" })}</span>
          )}
          {novel.age_limit === "r18" ? <span className="age-chip age-chip-r18">R18</span> : null}
          {novel.age_limit === "r15" ? <span className="age-chip">R15</span> : null}
          {showFreshBadge ? <span className="age-chip novel-fresh-chip">{t({ ja: "新着", en: "New" })}</span> : null}
          <span className="age-chip novel-type-chip">{novel.creative_type === "fanfic" ? "fanfic" : "original"}</span>
        </div>

        {showDescription ? (
          <p className="novel-card-description">
            {shortDescription || t({ ja: "説明がありません。", en: "No description." })}
          </p>
        ) : null}

        <div className="novel-card-stats">
          <span>{t({ ja: "LIKE", en: "Likes" })}: {novel.like_count ?? 0}</span>
          <span>{t({ ja: "コメント", en: "Comments" })}: {novel.comment_count ?? 0}</span>
          <span>{t({ ja: "お気に入り", en: "Favorites" })}: {novel.favorite_count ?? 0}</span>
          <span>{t({ ja: "閲覧", en: "Views" })}: {novel.view_count ?? 0}</span>
          <span>{t({ ja: "文字数", en: "Chars" })}: {novel.total_char_count ?? 0}</span>
        </div>

        {tagNames.length > 0 ? (
          <div className="tag-chip-row tag-chip-row-reserve-2lines">
            {tagNames.map((name) =>
              typeof onTagClick === "function" ? (
                <button
                  key={`${novel.id}-${name}`}
                  type="button"
                  className="tag-chip tag-chip-button"
                  onClick={() => onTagClick(name)}
                >
                  #{name}
                </button>
              ) : (
                <TagChipLink key={`${novel.id}-${name}`} name={name} />
              )
            )}
          </div>
        ) : null}

        {showCreatedAt && novel.created_at ? (
          <div className="novel-card-created-at">
            {t({ ja: "作成日時", en: "Created" })}: {new Date(novel.created_at).toLocaleString("ja-JP")}
          </div>
        ) : null}

        {typeof onLike === "function" || typeof onFavorite === "function" ? (
          <div className="novel-card-actions">
            {typeof onLike === "function" ? (
              <button type="button" className="btn btn-border" onClick={() => onLike(novel)}>
                {novel.is_liked
                  ? t({ ja: "♥ いいね済み", en: "♥ Liked" })
                  : t({ ja: "♡ いいね", en: "♡ Like" })}
              </button>
            ) : null}
            {typeof onFavorite === "function" ? (
              <button type="button" className="btn btn-border" onClick={() => onFavorite(novel)}>
                {novel.is_favorited
                  ? t({ ja: "★ ブックマーク済み", en: "★ Bookmarked" })
                  : t({ ja: "☆ ブックマーク", en: "☆ Bookmark" })}
              </button>
            ) : null}
          </div>
        ) : null}

        {footer ? <div className="novel-card-footer">{footer}</div> : null}
      </div>
    </article>
  );
}
