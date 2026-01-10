import { useEffect } from "react";
import { Link } from "react-router-dom";
import { trackEvent } from "../lib/analytics";
import { useI18n } from "../lib/i18n";

export default function AuthorLanding() {
  const { t, lang } = useI18n();
  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const previousTitle = document.title;
    const metaDescription = document.querySelector('meta[name="description"]');
    const previousDescription = metaDescription?.getAttribute("content");
    const nextTitle = t({
      ja: "作者向けLP｜小説投稿サイト",
      en: "For Authors | Novel Submission Site",
    });
    const nextDescription = t({
      ja: "初投稿でも埋もれない設計。評価やコメントが返ってくる、小説を書く人のための投稿サイト。無料・非公開OK・途中保存可。",
      en: "A posting site built for writers. First posts don't get buried, and feedback returns. Free, private OK, drafts supported.",
    });
    let createdMeta = null;

    document.title = nextTitle;
    if (metaDescription) {
      metaDescription.setAttribute("content", nextDescription);
    } else {
      const meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      meta.setAttribute("content", nextDescription);
      document.head.appendChild(meta);
      createdMeta = meta;
    }

    return () => {
      document.title = previousTitle;
      if (createdMeta) {
        createdMeta.remove();
        return;
      }
      if (metaDescription) {
        if (previousDescription === null) {
          metaDescription.removeAttribute("content");
        } else {
          metaDescription.setAttribute("content", previousDescription);
        }
      }
    };
  }, [lang, t]);

  useEffect(() => {
    trackEvent("author_lp_view", { page_path: "/authors" });
  }, []);

  const handleCtaClick = (label) => {
    trackEvent("author_lp_cta_click", { label, page_path: "/authors" });
  };

  return (
    <div className="author-lp">
      <section className="lp-hero">
        <div className="lp-hero-content">
          <p className="lp-eyebrow">{t({ ja: "作者向けランディング", en: "For Authors" })}</p>
          <h2 className="lp-hero-title">
            {t({ ja: "あなたの小説、", en: "Your novel," })}
            <br />
            {t({ ja: "発表しませんか。", en: "ready to publish?" })}
          </h2>
          <p className="lp-hero-lead">
            {t({
              ja: "書いたまま、下書きの中に眠らせていませんか。",
              en: "Are your drafts just sitting there?",
            })}
            <br />
            {t({ ja: "ここは、書く人のための投稿サイトです。", en: "This is a posting site for writers." })}
          </p>
          <p className="lp-hero-sub">
            {t({ ja: "初投稿でも埋もれない。", en: "Even your first post won't get buried." })}
            <br />
            {t({ ja: "書いた瞬間から、反応が返ってくる設計。", en: "Get responses from the moment you post." })}
          </p>
          <div className="lp-cta-row">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("hero_primary")}
            >
              {t({ ja: "今すぐ小説を書く", en: "Start writing now" })}
            </Link>
          </div>
          <p className="lp-note">
            {t({
              ja: "※無料・非公開OK・途中保存できます（公開は後からでOK）",
              en: "Free. Private OK. Drafts supported (publish later).",
            })}
          </p>
        </div>
        <div className="lp-hero-art" aria-hidden="true">
          <div className="lp-orbit lp-orbit-1" />
          <div className="lp-orbit lp-orbit-2" />
          <div className="lp-hero-card">
            <p className="lp-card-label">{t({ ja: "初投稿専用", en: "First Post" })}</p>
            <p className="lp-card-title">{t({ ja: "今、書き始める入口", en: "A place to start now" })}</p>
            <p className="lp-card-text">
              {t({
                ja: "迷っているなら、まず1行。下書きから始められます。",
                en: "If you're hesitating, start with one line. Drafts welcome.",
              })}
            </p>
          </div>
          <div className="lp-hero-card lp-hero-card-secondary">
            <p className="lp-card-label">{t({ ja: "反応の文化", en: "Culture of feedback" })}</p>
            <p className="lp-card-title">{t({ ja: "作者同士が支え合う", en: "Writers support each other" })}</p>
            <p className="lp-card-text">
              {t({ ja: "感想が、書き続ける力になる。", en: "Feedback keeps you writing." })}
            </p>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-muted">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">{t({ ja: "セクション1：共感と代弁", en: "Section 1: Empathy" })}</p>
          <h3 className="lp-section-title">
            {t({ ja: "書きたい気持ちは、ある。でも――", en: "You want to write, but..." })}
          </h3>
          <div className="lp-grid lp-grid-4">
            <div className="lp-card">
              <p>{t({ ja: "完成していない気がする", en: "It feels unfinished" })}</p>
            </div>
            <div className="lp-card">
              <p>{t({ ja: "下手だと思われそう", en: "People might think it's bad" })}</p>
            </div>
            <div className="lp-card">
              <p>{t({ ja: "どう始めればいいか分からない", en: "Not sure how to start" })}</p>
            </div>
            <div className="lp-card">
              <p>{t({ ja: "投稿する場所が分からない", en: "Don't know where to post" })}</p>
            </div>
          </div>
          <p className="lp-section-lead">
            {t({ ja: "その迷いのせいで、", en: "Because of that hesitation," })}
            <br />
            {t({
              ja: "書いた言葉が、誰にも届かないまま消えていく。",
              en: "your words disappear without reaching anyone.",
            })}
          </p>
          <p className="lp-section-strong">
            {t({ ja: "ここは、そのための場所じゃありません。", en: "This isn't that kind of place." })}
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section1")}
            >
              {t({ ja: "1行だけ、書いてみる", en: "Write just one line" })}
            </Link>
            <p className="lp-note">
              {t({
                ja: "※公開しなくて大丈夫。下書きから始められます。",
                en: "No need to publish. Start with a draft.",
              })}
            </p>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">{t({ ja: "セクション2：価値提示（断言）", en: "Section 2: Value" })}</p>
          <h3 className="lp-section-title">
            {t({ ja: "初投稿でも、ちゃんと見てもらえる理由があります。", en: "Reasons your first post gets seen." })}
          </h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-feature">
              <h4>{t({ ja: "初投稿・新着専用の露出枠", en: "Visibility slots for first & new posts" })}</h4>
              <p>{t({ ja: "最初の一作が、埋もれない設計。", en: "Designed so your first work isn't buried." })}</p>
            </div>
            <div className="lp-feature">
              <h4>{t({ ja: "ランキングに依存しない表示設計", en: "A feed that doesn't rely on rankings" })}</h4>
              <p>{t({ ja: "数字よりも、作品の新鮮さを優先。", en: "Freshness over numbers." })}</p>
            </div>
            <div className="lp-feature">
              <h4>{t({ ja: "作者同士が反応し合う文化", en: "A culture of mutual feedback" })}</h4>
              <p>{t({ ja: "読む側も、書く側も、近い距離で。", en: "Readers and writers stay close." })}</p>
            </div>
          </div>
          <p className="lp-section-strong">
            {t({ ja: "有名じゃなくていい。完璧じゃなくていい。", en: "You don't need to be famous or perfect." })}
            <br />
            {t({ ja: "「最初の一作」が届く導線があります。", en: "There are paths for your first work to be found." })}
          </p>
          <p className="lp-section-lead">
            {t({ ja: "初投稿が見られる導線を、最初から用意しています。", en: "Discovery paths are ready from the start." })}
          </p>
          <p className="lp-note">
            {t({
              ja: "※初投稿は新着枠に表示されます（公開・非公開はいつでも切替可）",
              en: "First posts appear in new arrivals (toggle public/private anytime).",
            })}
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section2")}
            >
              {t({ ja: "初投稿を書いてみる", en: "Write your first post" })}
            </Link>
            <p className="lp-note">
              {t({ ja: "※非公開OK。まずは非公開の下書きでもOK", en: "Private OK. Start with a private draft." })}
            </p>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-dark">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">{t({ ja: "セクション3：承認欲求の直撃", en: "Section 3: Real Feedback" })}</p>
          <h3 className="lp-section-title">
            {t({ ja: "反応があるから、書き続けられる。", en: "Feedback helps you keep writing." })}
          </h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-card lp-card-dark">
              <p>{t({ ja: "読まれたら分かる", en: "You can tell when it's read" })}</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>{t({ ja: "いいねやコメントが届く", en: "Likes and comments arrive" })}</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>{t({ ja: "感想が、作者に直接返ってくる", en: "Feedback reaches you directly" })}</p>
            </div>
          </div>
          <p className="lp-section-lead">
            {t({ ja: "数字じゃない。", en: "It's not about numbers." })}
            <br />
            {t({
              ja: "「誰かが読んだ」という実感が、次の一文を連れてくる。",
              en: "The feeling of being read brings the next line.",
            })}
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary lp-cta-white"
              onClick={() => handleCtaClick("section3")}
            >
              {t({ ja: "感想がもらえる場所で書く", en: "Write where feedback comes back" })}
            </Link>
            <p className="lp-note">
              {t({ ja: "※非公開OK。まずは短編でも、1話でも", en: "Private OK. Start with a short story or one episode." })}
            </p>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">{t({ ja: "セクション4：ハードル破壊", en: "Section 4: Lower the barrier" })}</p>
          <h3 className="lp-section-title">
            {t({ ja: "書くのに、才能はいりません。", en: "You don't need talent to write." })}
          </h3>
          <div className="lp-grid lp-grid-4">
            <div className="lp-feature">
              <h4>{t({ ja: "スマホでも書ける", en: "Write on your phone" })}</h4>
              <p>{t({ ja: "思いついた瞬間に、すぐ書ける。", en: "Write the moment inspiration hits." })}</p>
            </div>
            <div className="lp-feature">
              <h4>{t({ ja: "途中保存できる", en: "Save midway" })}</h4>
              <p>{t({ ja: "書きかけでも、安心して止められる。", en: "Pause safely even mid-draft." })}</p>
            </div>
            <div className="lp-feature">
              <h4>{t({ ja: "何度でも書き直せる", en: "Rewrite anytime" })}</h4>
              <p>{t({ ja: "下書きから公開まで、やり直し自由。", en: "Revise freely from draft to publish." })}</p>
            </div>
            <div className="lp-feature">
              <h4>{t({ ja: "公開・非公開はいつでも切替", en: "Toggle public/private anytime" })}</h4>
              <p>{t({ ja: "公開タイミングは自分で選べる。", en: "Choose your own publishing timing." })}</p>
            </div>
          </div>
          <p className="lp-section-strong">
            {t({ ja: "うまく書こうとしなくていい。", en: "You don't have to be perfect." })}
            <br />
            {t({ ja: "書き始めるだけでいい。", en: "Just start writing." })}
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section4")}
            >
              {t({ ja: "下手でもいいから、書く", en: "Write anyway" })}
            </Link>
            <p className="lp-note">
              {t({ ja: "※非公開OK。非公開のまま練習できます", en: "Private OK. Practice without publishing." })}
            </p>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-muted">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">{t({ ja: "セクション5：AI補助", en: "Section 5: AI assistance" })}</p>
          <h3 className="lp-section-title">
            {t({ ja: "詰まったら、AIに頼っていい。", en: "When you're stuck, lean on AI." })}
          </h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-card">
              <p>{t({ ja: "プロットの相談", en: "Plot brainstorming" })}</p>
            </div>
            <div className="lp-card">
              <p>{t({ ja: "表現の言い換え", en: "Rewrite wording" })}</p>
            </div>
            <div className="lp-card">
              <p>{t({ ja: "続きのアイデア出し", en: "Ideas for what comes next" })}</p>
            </div>
          </div>
          <p className="lp-section-lead">
            {t({ ja: "AIは代わりに書きません。", en: "AI doesn't write for you." })}
            <br />
            {t({ ja: "あなたが書くための補助輪です。", en: "It's training wheels for your writing." })}
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section5")}
            >
              {t({ ja: "詰まったらAIに頼って書く", en: "Write with AI when stuck" })}
            </Link>
            <p className="lp-note">
              {t({ ja: "※非公開OK。あなたの文章を主役にします", en: "Private OK. Your words stay center stage." })}
            </p>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">{t({ ja: "セクション6：作者の声", en: "Section 6: Voices" })}</p>
          <h3 className="lp-section-title">
            {t({ ja: "短い言葉が、背中を押す。", en: "A few words can push you forward." })}
          </h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-quote">
              <p>
                {t({
                  ja: "初投稿で、ちゃんとコメントがついた。それだけで救われた。",
                  en: "On my first post, I got comments. That alone saved me.",
                })}
              </p>
            </div>
            <div className="lp-quote">
              <p>
                {t({
                  ja: "他の場所より、反応が早かった。「書いていいんだ」と思えた。",
                  en: "Responses came faster than elsewhere. I felt it was okay to write.",
                })}
              </p>
            </div>
            <div className="lp-quote">
              <p>
                {t({
                  ja: "完璧じゃないまま出したけど、それでも読んでもらえた。",
                  en: "I posted before it was perfect, and people still read it.",
                })}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-dark">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">{t({ ja: "セクション7：安心材料", en: "Section 7: Peace of mind" })}</p>
          <h3 className="lp-section-title">
            {t({ ja: "始めるのに、リスクはありません。", en: "No risk to begin." })}
          </h3>
          <div className="lp-grid lp-grid-4">
            <div className="lp-card lp-card-dark">
              <p>{t({ ja: "完全無料", en: "Completely free" })}</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>{t({ ja: "匿名OK", en: "Anonymous OK" })}</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>{t({ ja: "やめたくなったら、いつでもやめられる", en: "Quit anytime" })}</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>{t({ ja: "残るのは、書いた言葉だけ", en: "Only your words remain" })}</p>
            </div>
          </div>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary lp-cta-white"
              onClick={() => handleCtaClick("section7")}
            >
              {t({ ja: "非公開で、今すぐ書き始める", en: "Start writing privately now" })}
            </Link>
            <p className="lp-note">
              {t({ ja: "※非公開OK。公開は後からでOK", en: "Private OK. Publish later if you want." })}
            </p>
          </div>
        </div>
      </section>

      <section className="lp-cta-final">
        <div className="lp-cta-inner">
          <h3>{t({ ja: "書くか、また先延ばしにするか。", en: "Write now, or postpone again." })}</h3>
          <p>
            {t({ ja: "今日書かなかった一文は、", en: "The line you don't write today" })}
            <br />
            {t({ ja: "明日も、書かれないままです。", en: "won't be written tomorrow either." })}
          </p>
          <Link
            to="/novels/new"
            className="lp-cta lp-cta-primary"
            onClick={() => handleCtaClick("final")}
          >
            {t({ ja: "今すぐ小説を書く", en: "Start writing now" })}
          </Link>
          <p className="lp-note">
            {t({ ja: "※初投稿まで最短3分（非公開OK）", en: "First post in as little as 3 minutes (private OK)." })}
          </p>
        </div>
      </section>
    </div>
  );
}
