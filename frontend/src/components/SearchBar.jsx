// src/components/SearchBar.jsx （パスは今の構成に合わせてね）
export default function SearchBar({ q, tag, onChangeQ, onChangeTag }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("検索:", q, tag);
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

