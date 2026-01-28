// frontend/src/components/SearchBar.jsx
import { useI18n } from "../lib/i18n";

export default function SearchBar({
  query,
  excludeQuery,
  onChangeQuery,
  onChangeExcludeQuery,
  onSearch,
}) {
  const { t } = useI18n();
  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSearch) {
      onSearch({ query, excludeQuery }); // ← 親に「検索して」と依頼する
    }
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder={t({
          ja: "検索: タイトル/本文/概要/タグ(空白・カンマ)/@ユーザー",
          en: "Search: title/body/summary/tags (space/comma)/@user",
        })}
        value={query}
        onChange={(e) => onChangeQuery(e.target.value)}
        className="search-input"
      />
      <input
        type="text"
        placeholder={t({
          ja: "除外: タイトル/本文/概要/タグ(空白・カンマ)/@ユーザー",
          en: "Exclude: title/body/summary/tags (space/comma)/@user",
        })}
        value={excludeQuery}
        onChange={(e) => onChangeExcludeQuery(e.target.value)}
        className="search-input"
      />

      <button type="submit" className="search-button">
        {t({ ja: "検索", en: "Search" })}
      </button>
    </form>
  );
}
