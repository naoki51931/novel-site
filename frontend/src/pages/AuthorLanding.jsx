import { useEffect } from "react";
import { Link } from "react-router-dom";
import { trackEvent } from "../lib/analytics";

export default function AuthorLanding() {
  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const previousTitle = document.title;
    const metaDescription = document.querySelector('meta[name="description"]');
    const previousDescription = metaDescription?.getAttribute("content");
    const nextTitle = "作者向けLP｜小説投稿サイト";
    const nextDescription =
      "初投稿でも埋もれない設計。評価やコメントが返ってくる、小説を書く人のための投稿サイト。無料・非公開OK・途中保存可。";
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
  }, []);

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
          <p className="lp-eyebrow">作者向けランディング</p>
          <h2 className="lp-hero-title">
            あなたの小説、
            <br />
            発表しませんか。
          </h2>
          <p className="lp-hero-lead">
            書いたまま、下書きの中に眠らせていませんか。
            <br />
            ここは、書く人のための投稿サイトです。
          </p>
          <p className="lp-hero-sub">
            初投稿でも埋もれない。
            <br />
            書いた瞬間から、反応が返ってくる設計。
          </p>
          <div className="lp-cta-row">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("hero_primary")}
            >
              今すぐ小説を書く
            </Link>
          </div>
          <p className="lp-note">※無料・非公開OK・途中保存できます（公開は後からでOK）</p>
        </div>
        <div className="lp-hero-art" aria-hidden="true">
          <div className="lp-orbit lp-orbit-1" />
          <div className="lp-orbit lp-orbit-2" />
          <div className="lp-hero-card">
            <p className="lp-card-label">初投稿専用</p>
            <p className="lp-card-title">今、書き始める入口</p>
            <p className="lp-card-text">
              迷っているなら、まず1行。下書きから始められます。
            </p>
          </div>
          <div className="lp-hero-card lp-hero-card-secondary">
            <p className="lp-card-label">反応の文化</p>
            <p className="lp-card-title">作者同士が支え合う</p>
            <p className="lp-card-text">感想が、書き続ける力になる。</p>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-muted">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">セクション1：共感と代弁</p>
          <h3 className="lp-section-title">書きたい気持ちは、ある。でも――</h3>
          <div className="lp-grid lp-grid-4">
            <div className="lp-card">
              <p>完成していない気がする</p>
            </div>
            <div className="lp-card">
              <p>下手だと思われそう</p>
            </div>
            <div className="lp-card">
              <p>どう始めればいいか分からない</p>
            </div>
            <div className="lp-card">
              <p>投稿する場所が分からない</p>
            </div>
          </div>
          <p className="lp-section-lead">
            その迷いのせいで、
            <br />
            書いた言葉が、誰にも届かないまま消えていく。
          </p>
          <p className="lp-section-strong">
            ここは、そのための場所じゃありません。
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section1")}
            >
              1行だけ、書いてみる
            </Link>
            <p className="lp-note">※公開しなくて大丈夫。下書きから始められます。</p>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">セクション2：価値提示（断言）</p>
          <h3 className="lp-section-title">初投稿でも、ちゃんと見てもらえる理由があります。</h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-feature">
              <h4>初投稿・新着専用の露出枠</h4>
              <p>最初の一作が、埋もれない設計。</p>
            </div>
            <div className="lp-feature">
              <h4>ランキングに依存しない表示設計</h4>
              <p>数字よりも、作品の新鮮さを優先。</p>
            </div>
            <div className="lp-feature">
              <h4>作者同士が反応し合う文化</h4>
              <p>読む側も、書く側も、近い距離で。</p>
            </div>
          </div>
          <p className="lp-section-strong">
            有名じゃなくていい。完璧じゃなくていい。
            <br />
            「最初の一作」が届く導線があります。
          </p>
          <p className="lp-section-lead">初投稿が見られる導線を、最初から用意しています。</p>
          <p className="lp-note">
            ※初投稿は新着枠に表示されます（公開・非公開はいつでも切替可）
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section2")}
            >
              初投稿を書いてみる
            </Link>
            <p className="lp-note">※非公開OK。まずは非公開の下書きでもOK</p>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-dark">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">セクション3：承認欲求の直撃</p>
          <h3 className="lp-section-title">反応があるから、書き続けられる。</h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-card lp-card-dark">
              <p>読まれたら分かる</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>いいねやコメントが届く</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>感想が、作者に直接返ってくる</p>
            </div>
          </div>
          <p className="lp-section-lead">
            数字じゃない。
            <br />
            「誰かが読んだ」という実感が、次の一文を連れてくる。
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary lp-cta-white"
              onClick={() => handleCtaClick("section3")}
            >
              感想がもらえる場所で書く
            </Link>
            <p className="lp-note">※非公開OK。まずは短編でも、1話でも</p>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">セクション4：ハードル破壊</p>
          <h3 className="lp-section-title">書くのに、才能はいりません。</h3>
          <div className="lp-grid lp-grid-4">
            <div className="lp-feature">
              <h4>スマホでも書ける</h4>
              <p>思いついた瞬間に、すぐ書ける。</p>
            </div>
            <div className="lp-feature">
              <h4>途中保存できる</h4>
              <p>書きかけでも、安心して止められる。</p>
            </div>
            <div className="lp-feature">
              <h4>何度でも書き直せる</h4>
              <p>下書きから公開まで、やり直し自由。</p>
            </div>
            <div className="lp-feature">
              <h4>公開・非公開はいつでも切替</h4>
              <p>公開タイミングは自分で選べる。</p>
            </div>
          </div>
          <p className="lp-section-strong">
            うまく書こうとしなくていい。
            <br />
            書き始めるだけでいい。
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section4")}
            >
              下手でもいいから、書く
            </Link>
            <p className="lp-note">※非公開OK。非公開のまま練習できます</p>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-muted">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">セクション5：AI補助</p>
          <h3 className="lp-section-title">詰まったら、AIに頼っていい。</h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-card">
              <p>プロットの相談</p>
            </div>
            <div className="lp-card">
              <p>表現の言い換え</p>
            </div>
            <div className="lp-card">
              <p>続きのアイデア出し</p>
            </div>
          </div>
          <p className="lp-section-lead">
            AIは代わりに書きません。
            <br />
            あなたが書くための補助輪です。
          </p>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary"
              onClick={() => handleCtaClick("section5")}
            >
              詰まったらAIに頼って書く
            </Link>
            <p className="lp-note">※非公開OK。あなたの文章を主役にします</p>
          </div>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">セクション6：作者の声</p>
          <h3 className="lp-section-title">短い言葉が、背中を押す。</h3>
          <div className="lp-grid lp-grid-3">
            <div className="lp-quote">
              <p>初投稿で、ちゃんとコメントがついた。それだけで救われた。</p>
            </div>
            <div className="lp-quote">
              <p>他の場所より、反応が早かった。「書いていいんだ」と思えた。</p>
            </div>
            <div className="lp-quote">
              <p>完璧じゃないまま出したけど、それでも読んでもらえた。</p>
            </div>
          </div>
        </div>
      </section>

      <section className="lp-section lp-section-dark">
        <div className="lp-section-inner">
          <p className="lp-section-kicker">セクション7：安心材料</p>
          <h3 className="lp-section-title">始めるのに、リスクはありません。</h3>
          <div className="lp-grid lp-grid-4">
            <div className="lp-card lp-card-dark">
              <p>完全無料</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>匿名OK</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>やめたくなったら、いつでもやめられる</p>
            </div>
            <div className="lp-card lp-card-dark">
              <p>残るのは、書いた言葉だけ</p>
            </div>
          </div>
          <div className="lp-cta-block">
            <Link
              to="/novels/new"
              className="lp-cta lp-cta-primary lp-cta-white"
              onClick={() => handleCtaClick("section7")}
            >
              非公開で、今すぐ書き始める
            </Link>
            <p className="lp-note">※非公開OK。公開は後からでOK</p>
          </div>
        </div>
      </section>

      <section className="lp-cta-final">
        <div className="lp-cta-inner">
          <h3>書くか、また先延ばしにするか。</h3>
          <p>
            今日書かなかった一文は、
            <br />
            明日も、書かれないままです。
          </p>
          <Link
            to="/novels/new"
            className="lp-cta lp-cta-primary"
            onClick={() => handleCtaClick("final")}
          >
            今すぐ小説を書く
          </Link>
          <p className="lp-note">※初投稿まで最短3分（非公開OK）</p>
        </div>
      </section>
    </div>
  );
}
