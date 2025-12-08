// frontend/src/components/SearchBar.jsx
export default function SearchBar({ q, tag, onChangeQ, onChangeTag, onSearch }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSearch) {
      onSearch();        // ← 親に「検索して」と依頼する
    }
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="タイトル検索..."
        value={q}
        onChange={(e) => onChangeQ(e.target.value)}
        className="search-input"
      />

      <input
        type="text"
        placeholder="タグ検索..."
        value={tag}
        onChange={(e) => onChangeTag(e.target.value)}
        className="search-tag-input"
      />

      <button type="submit" className="search-button">
        検索
      </button>
    </form>
  );
}

