import { Link } from "react-router-dom";

export const buildTagSearchUrl = (tagName) => {
  const name = (tagName ?? "").toString().trim();
  const params = new URLSearchParams();
  params.set("tag", name);
  return `/?${params.toString()}`;
};

export default function TagChipLink({ name }) {
  const label = (name ?? "").toString().trim();
  if (!label) return null;

  return (
    <Link
      to={buildTagSearchUrl(label)}
      className="tag-chip"
      aria-label={`タグ「${label}」で検索`}
      title={`タグ「${label}」で検索`}
    >
      #{label}
    </Link>
  );
}

