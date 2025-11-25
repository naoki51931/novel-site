export default function SearchBar({ q, tag, onChangeQ, onChangeTag }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("検索:", q, tag); // デバッグ用
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        marginBottom: 16,
        display: "flex",
        gap: 12,
        alignItems: "center",
      }}
    >
      <input
        type="text"
        placeholder="タイトル検索..."
        value={q}
        onChange={(e) => onChangeQ(e.target.value)}
        style={{ padding: "6px 8px", flex: 1 }}
      />

      <input
        type="text"
        placeholder="タグ検索..."
        value={tag}
        onChange={(e) => onChangeTag(e.target.value)}
        style={{ padding: "6px 8px", width: 150 }}
      />

      <button
        type="submit"
        style={{
          padding: "6px 12px",
          background: "#333",
          color: "#fff",
          border: "none",
          borderRadius: 4,
          cursor: "pointer",
        }}
      >
        検索
      </button>
    </form>
  );
}
