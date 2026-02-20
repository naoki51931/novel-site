import { useI18n } from "../lib/i18n";

const SITE_LINKS = [
  {
    key: "main",
    href: "https://shosetsu-toukou-site.org/",
    jaTitle: "小説投稿サイトLexis",
    enTitle: "Lexis",
    jaDesc: "総合ジャンルのメイン投稿サイト",
    enDesc: "Main all-genre posting site",
  },
  {
    key: "romance",
    href: "https://renai.shosetsu-toukou-site.org/",
    jaTitle: "恋愛小説Lexis",
    enTitle: "Romance Lexis",
    jaDesc: "恋愛ジャンル特化の投稿サイト",
    enDesc: "Romance-focused posting site",
  },
  {
    key: "history",
    href: "https://rekishi.shosetsu-toukou-site.org/",
    jaTitle: "歴史小説Lexis",
    enTitle: "History Lexis",
    jaDesc: "歴史・時代小説特化の投稿サイト",
    enDesc: "History-focused posting site",
  },
];

export default function AllSites() {
  const { t } = useI18n();

  return (
    <section className="all-sites-page">
      <div className="all-sites-header">
        <h2>{t({ ja: "Lexis 総合ポータル", en: "Lexis Portal" })}</h2>
        <p>
          {t({
            ja: "目的にあわせて3つのLexisサイトへ移動できます。",
            en: "Choose a Lexis site by purpose.",
          })}
        </p>
      </div>
      <div className="all-sites-grid">
        {SITE_LINKS.map((site) => (
          <a
            key={site.key}
            className="all-site-card"
            href={site.href}
          >
            <h3>{t({ ja: site.jaTitle, en: site.enTitle })}</h3>
            <p>{t({ ja: site.jaDesc, en: site.enDesc })}</p>
            <span className="all-site-url">{site.href}</span>
          </a>
        ))}
      </div>
    </section>
  );
}
