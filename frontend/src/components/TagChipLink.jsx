import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export const buildTagSearchUrl = (tagName) => {
  const name = (tagName ?? "").toString().trim();
  const params = new URLSearchParams();
  params.set("tag", name);
  return `/?${params.toString()}`;
};

export default function TagChipLink({ name }) {
  const { t } = useI18n();
  const label = (name ?? "").toString().trim();
  if (!label) return null;

  return (
    <Link
      to={buildTagSearchUrl(label)}
      className="tag-chip"
      aria-label={t(
        { ja: "タグ「{{tag}}」で検索", en: "Search tag \"{{tag}}\"" },
        { tag: label }
      )}
      title={t(
        { ja: "タグ「{{tag}}」で検索", en: "Search tag \"{{tag}}\"" },
        { tag: label }
      )}
    >
      #{label}
    </Link>
  );
}
