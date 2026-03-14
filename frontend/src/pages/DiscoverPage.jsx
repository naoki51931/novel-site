import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import NovelCard from "../components/NovelCard.jsx";
import { useI18n } from "../lib/i18n";
import { getApiBase } from "../lib/apiBase";
import { filterR18Novels, useShowR18ByDisplaySetting } from "../lib/r18Display";

const API_BASE = getApiBase();

export default function DiscoverPage() {
  const location = useLocation();
  const { t, lang } = useI18n();
  const showR18 = useShowR18ByDisplaySetting();
  const mode = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return String(params.get("mode") || "").trim().toLowerCase();
  }, [location.search]);
  const [trendingTags, setTrendingTags] = useState([]);
  const [seriesList, setSeriesList] = useState([]);
  const [pickups, setPickups] = useState([]);
  const [recommended, setRecommended] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const prevTitle = document.title;
    const metaDescription = document.querySelector('meta[name="description"]');
    const prevDescription = metaDescription?.getAttribute("content");
    const isRecommended = mode === "recommended";
    const isPickups = mode === "pickups";
    const isTags = mode === "tags";
    const isSeries = mode === "series";
    document.title = isRecommended
      ? t({ ja: "おすすめ発見｜小説投稿サイトLexis", en: "Recommended Discover | Lexis" })
      : isPickups
      ? t({ ja: "ピックアップ発見｜小説投稿サイトLexis", en: "Pickups Discover | Lexis" })
      : isTags
      ? t({ ja: "タグ発見｜小説投稿サイトLexis", en: "Tag Discover | Lexis" })
      : isSeries
      ? t({ ja: "シリーズ発見｜小説投稿サイトLexis", en: "Series Discover | Lexis" })
      : t({ ja: "発見ページ｜小説投稿サイトLexis", en: "Discover | Lexis" });
    const desc = isRecommended
      ? t({
          ja: "おすすめ作品を中心に、あなた向けの作品探索を行えます。",
          en: "Focus on recommended works tailored for you.",
        })
      : t({
          ja: "トレンドタグ、ピックアップ特集、シリーズまとめから作品を見つけられます。",
          en: "Discover novels via trending tags, pickups, and series collections.",
        });
    if (metaDescription) metaDescription.setAttribute("content", desc);
    return () => {
      document.title = prevTitle;
      if (metaDescription) {
        if (prevDescription == null) metaDescription.removeAttribute("content");
        else metaDescription.setAttribute("content", prevDescription);
      }
    };
  }, [t, lang, mode]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        const authHeaders = token ? { Authorization: `Bearer ${token}` } : undefined;

        const recParams = new URLSearchParams();
        recParams.set("limit", "20");
        const [resTags, resSeries, resPickups, resRecommended] = await Promise.all([
          fetch(`${API_BASE}/api/trending-tags?days=7&limit=20`, { cache: "no-store" }),
          fetch(`${API_BASE}/api/series?limit=20`, { cache: "no-store" }),
          token
            ? fetch(`${API_BASE}/api/feed/pickups?limit=12`, {
                headers: authHeaders,
                cache: "no-store",
              })
            : Promise.resolve(new Response("[]", { status: 200 })),
          token
            ? fetch(`${API_BASE}/api/feed/recommended?${recParams.toString()}`, {
                headers: authHeaders,
                cache: "no-store",
              })
            : Promise.resolve(new Response("[]", { status: 200 })),
        ]);

        const tagsData = await resTags.json().catch(() => []);
        const seriesData = await resSeries.json().catch(() => []);
        const pickupsData = await resPickups.json().catch(() => []);
        const recommendedData = await resRecommended.json().catch(() => []);

        if (!resTags.ok) {
          throw new Error(
            tagsData?.detail || t({ ja: "トレンドタグの取得に失敗しました。", en: "Failed to load trending tags." })
          );
        }
        if (!resSeries.ok) {
          throw new Error(
            seriesData?.detail || t({ ja: "シリーズ一覧の取得に失敗しました。", en: "Failed to load series." })
          );
        }

        setTrendingTags(Array.isArray(tagsData) ? tagsData : []);
        setSeriesList(Array.isArray(seriesData) ? seriesData : []);
        setPickups(Array.isArray(pickupsData) ? pickupsData : []);
        setRecommended(Array.isArray(recommendedData) ? recommendedData : []);
      } catch (e) {
        console.error(e);
        setError(e.message || t({ ja: "取得に失敗しました。", en: "Failed to load data." }));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [t]);

  const showTags = mode === "" || mode === "tags";
  const showPickups = mode === "" || mode === "pickups";
  const showSeries = mode === "" || mode === "series";
  const showRecommended = mode === "recommended";
  const pickupsVisible = filterR18Novels(pickups, showR18);
  const recommendedVisible = filterR18Novels(recommended, showR18);

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 8 }}>
        {showRecommended ? t({ ja: "おすすめ発見", en: "Recommended Discover" }) : t({ ja: "発見", en: "Discover" })}
      </h2>
      <p style={{ marginTop: 0, color: "var(--muted-text)" }}>
        {showRecommended
          ? t({
              ja: "あなた向けのおすすめ作品から探索できます。",
              en: "Start exploring with recommendations tailored for you.",
            })
          : t({
              ja: "トレンドタグ・ピックアップ特集・シリーズまとめから作品を掘れます。",
              en: "Dig into works from trending tags, pickups, and series collections.",
            })}
      </p>
      {error ? <p style={{ color: "red" }}>{error}</p> : null}
      {loading ? (
        <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
      ) : (
        <>
          {showRecommended && (
            <section style={{ marginBottom: 24 }}>
              <div className="section-heading-row">
                <h3 className="section-heading-title">{t({ ja: "あなたへのおすすめ", en: "Recommended for You" })}</h3>
                <Link to="/" className="section-heading-more">{t({ ja: "ホームへ", en: "Back to Home" })}</Link>
              </div>
              {recommendedVisible.length === 0 ? (
                <p style={{ color: "var(--muted-text)" }}>
                  {t({
                    ja: "おすすめはまだありません。ログイン後に閲覧・いいね・ブックマークを増やすと精度が上がります。",
                    en: "No recommendations yet. Log in and interact more to improve results.",
                  })}
                </p>
              ) : (
                <div className="novel-grid">
                  {recommendedVisible.map((novel) => (
                    <NovelCard
                      key={`discover-recommended-${novel.id}`}
                      novel={novel}
                      t={t}
                      apiBase={API_BASE}
                      maxTags={4}
                      descriptionMax={100}
                      footer={
                        <Link className="btn btn-border" to={`/novels/${novel.id}`}>
                          {t({ ja: "続きを読む", en: "Read more" })}
                        </Link>
                      }
                    />
                  ))}
                </div>
              )}
            </section>
          )}

          {showTags && (
            <section style={{ marginBottom: 24 }}>
              <div className="section-heading-row">
                <h3 className="section-heading-title">{t({ ja: "トレンドタグ", en: "Trending Tags" })}</h3>
              </div>
              {trendingTags.length === 0 ? (
                <p style={{ color: "var(--muted-text)" }}>
                  {t({ ja: "トレンドタグはまだありません。", en: "No trending tags yet." })}
                </p>
              ) : (
                <div className="tag-chip-row">
                  {trendingTags.map((tag) => (
                    <Link key={`discover-trend-${tag.id || tag.name}`} to={`/tags/${encodeURIComponent(tag.name || "")}`}>
                      #{tag.name} ({tag.novel_count ?? 0})
                    </Link>
                  ))}
                </div>
              )}
            </section>
          )}

          {showPickups && (
            <section style={{ marginBottom: 24 }}>
              <div className="section-heading-row">
                <h3 className="section-heading-title">{t({ ja: "ピックアップ特集", en: "Pickups" })}</h3>
              </div>
              {pickupsVisible.length === 0 ? (
                <p style={{ color: "var(--muted-text)" }}>
                  {t({
                    ja: "ログインすると、あなた向けのピックアップが表示されます。",
                    en: "Login to see personalized pickups.",
                  })}
                </p>
              ) : (
                <div className="novel-grid">
                  {pickupsVisible.map((novel) => (
                    <NovelCard
                      key={`discover-pickup-${novel.id}`}
                      novel={novel}
                      t={t}
                      apiBase={API_BASE}
                      maxTags={4}
                      descriptionMax={90}
                      footer={
                        <Link className="btn btn-border" to={`/novels/${novel.id}`}>
                          {t({ ja: "続きを読む", en: "Read more" })}
                        </Link>
                      }
                    />
                  ))}
                </div>
              )}
            </section>
          )}

          {showSeries && (
            <section style={{ marginBottom: 24 }}>
              <div className="section-heading-row">
                <h3 className="section-heading-title">{t({ ja: "シリーズまとめ", en: "Series Collections" })}</h3>
              </div>
              {seriesList.length === 0 ? (
                <p style={{ color: "var(--muted-text)" }}>
                  {t({ ja: "シリーズはまだありません。", en: "No series yet." })}
                </p>
              ) : (
                <div style={{ display: "grid", gap: 8 }}>
                  {seriesList.map((series) => (
                    <div key={`discover-series-${series.series_name}`} className="novel-card-ui">
                      <div className="novel-card-body">
                        <Link to={`/series/${encodeURIComponent(series.series_name || "")}`}>
                          {series.series_name}
                        </Link>
                        <span style={{ marginLeft: 8, color: "var(--muted-text)", fontSize: 12 }}>
                          {t({ ja: "{{count}} 作品", en: "{{count}} works" }, { count: series.novel_count ?? 0 })}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
