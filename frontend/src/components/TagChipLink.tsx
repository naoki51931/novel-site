import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export const buildTagSearchUrl = (tagName: string | null | undefined) => {
  const name = (tagName ?? "").toString().trim();
  if (!name) return "/tags";
  return `/tags/${encodeURIComponent(name)}`;
};

export default function TagChipLink({ name }: { name: string | null | undefined }) {
  const { t } = useI18n();
  const label = (name ?? "").toString().trim();
  if (!label) return null;

  return (
    <Link
      to={buildTagSearchUrl(label)}
      className="tag-chip"
      aria-label={t(
        { ja: "タグ「{{tag}}」の作品一覧へ", en: "View novels tagged \"{{tag}}\"" },
        { tag: label }
      )}
      title={t(
        { ja: "タグ「{{tag}}」の作品一覧へ", en: "View novels tagged \"{{tag}}\"" },
        { tag: label }
      )}
    >
      #{label}
    </Link>
  );
}
