// frontend/src/components/SearchBar.jsx
export default function SearchBar({ query, onChangeQuery, onSearch }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSearch) {
      onSearch(query); // ← 親に「検索して」と依頼する
    }
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="検索: タイトル/本文/概要/タグ(空白・カンマ)/@ユーザー"
        value={query}
        onChange={(e) => onChangeQuery(e.target.value)}
        className="search-input"
      />

      <button type="submit" className="search-button">
        検索
      </button>
    </form>
  );
}
