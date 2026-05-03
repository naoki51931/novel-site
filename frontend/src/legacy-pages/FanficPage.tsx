import Home from "./Home";
import { useI18n } from "../lib/i18n";

export default function FanficPage({
  query = "",
  excludeQuery = "",
  sort = "new",
  ageLimit = "",
}) {
  const { t } = useI18n();
  return (
    <div>
      <section style={{ margin: "12px 0 20px" }}>
        <h1 style={{ fontSize: 24, marginBottom: 8 }}>
          {t({ ja: "二次創作トップ", en: "Fanfic Top" })}
        </h1>
        <p style={{ color: "var(--muted-text)", lineHeight: 1.7 }}>
          {t({
            ja: "二次創作（fanfic）作品だけを表示します。新着・急上昇・ランキングから探せます。",
            en: "Shows only fanfic works. Discover through new, trending, and ranking sections.",
          })}
        </p>
      </section>
      <Home
        query={query}
        excludeQuery={excludeQuery}
        sort={sort}
        ageLimit={ageLimit}
        creativeType="fanfic"
      />
    </div>
  );
}
