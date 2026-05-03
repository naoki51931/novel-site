import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import TagChipLink from "../components/TagChipLink";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { filterR18Novels, useShowR18ByDisplaySetting } from "../lib/r18Display";

const API_BASE = getApiBase();

type SeriesNovel = {
  id: number | string;
  title?: string | null;
  series_order?: number | null;
  author_username?: string | null;
  creative_type?: string | null;
  age_limit?: string | null;
  tag_names?: Array<string | null | undefined> | null;
  description?: string | null;
};

const safeDecode = (value: string | undefined) => {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

export default function SeriesPage() {
  const { slug } = useParams();
  const { t } = useI18n();
  const showR18 = useShowR18ByDisplaySetting();
  const seriesName = useMemo(() => safeDecode(slug).trim(), [slug]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [novels, setNovels] = useState<SeriesNovel[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const encoded = encodeURIComponent(seriesName);
        const res = await fetch(`${API_BASE}/api/series/${encoded}/novels`);
        const data = await res.json().catch(() => []);
        if (!res.ok) {
          throw new Error(data?.detail || t({ ja: "シリーズ取得に失敗しました", en: "Failed to load series." }));
        }
        setNovels(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error(e);
        setError(getErrorMessage(e, t({ ja: "エラーが発生しました", en: "An error occurred." })));
      } finally {
        setLoading(false);
      }
    };
    if (!seriesName) {
      setError(t({ ja: "シリーズ名が不正です", en: "Invalid series name." }));
      setLoading(false);
      return;
    }
    load();
  }, [seriesName, t]);

  if (loading) return <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>;
  if (error) return <p style={{ color: "red" }}>{error}</p>;
  const novelsVisible = filterR18Novels(novels, showR18);

  return (
    <div>
      <h1 style={{ marginBottom: 10 }}>
        {t({ ja: "シリーズ", en: "Series" })}: {seriesName}
      </h1>
      {novelsVisible.length === 0 ? (
        <p>{t({ ja: "このシリーズの作品はありません。", en: "No novels in this series." })}</p>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {novelsVisible.map((novel) => (
            <article key={novel.id} className="novel-card" style={{ padding: 12 }}>
              <h4 style={{ margin: "0 0 6px" }}>
                <Link to={`/novels/${novel.id}`}>{novel.title}</Link>
                {novel.series_order != null ? (
                  <span style={{ marginLeft: 8, color: "var(--muted-text)", fontSize: 13 }}>
                    #{novel.series_order}
                  </span>
                ) : null}
              </h4>
              <div style={{ fontSize: 12, color: "var(--muted-text)", marginBottom: 8 }}>
                @{novel.author_username || "unknown"} / {novel.creative_type || "original"} / {novel.age_limit || "all"}
              </div>
              <div className="tag-chip-row" style={{ marginBottom: 8 }}>
                {(Array.isArray(novel.tag_names) ? novel.tag_names : []).slice(0, 4).map((name: string | null | undefined) => (
                  <TagChipLink key={`${novel.id}-${name}`} name={name} />
                ))}
              </div>
              {novel.description ? <p style={{ margin: 0 }}>{String(novel.description).slice(0, 140)}</p> : null}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
