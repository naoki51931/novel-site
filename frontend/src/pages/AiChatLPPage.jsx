import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

export default function AiChatLPPage() {
  const { t } = useI18n();
  const aiChatCtaPath = "/ai_chat?ref=ai_chat_lp";
  const subCtaStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 50,
    textAlign: "center",
  };

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "20px 8px 40px" }}>
      <section
        style={{
          borderRadius: 18,
          border: "1px solid #bfd8f8",
          padding: "24px 20px",
          background: "linear-gradient(135deg, #e8f2ff 0%, #f3f8ff 45%, #ffffff 100%)",
          boxShadow: "0 12px 30px rgba(8, 56, 120, 0.08)",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "inline-block", padding: "4px 10px", borderRadius: 999, background: "#0a3f8b", color: "#fff", fontSize: 12, fontWeight: 700 }}>
          {t({ ja: "AI CHAT", en: "AI CHAT" })}
        </div>
        <h2 style={{ margin: "12px 0 8px", fontSize: "clamp(1.5rem, 2.7vw, 2rem)", lineHeight: 1.24 }}>
          {t({ ja: "キャラ生成して、会話する。", en: "Generate characters and chat." })}
          <br />
          {t({ ja: "AIチャットを最短で始める。", en: "Start AI chat in minutes." })}
        </h2>
        <p style={{ margin: "0 0 6px", color: "#26456d", lineHeight: 1.7, fontSize: "0.97rem" }}>
          {t({
            ja: "オリジナルキャラも二次創作キャラも作成でき、会話ログはそのままAI小説化できます。設定を調整しながら、好みの会話体験を組み立てられます。",
            en: "Create original or fan-work characters, chat with them, and turn conversations into AI novels.",
          })}
        </p>
        <p style={{ margin: "0 0 14px", color: "#123865", fontWeight: 700, fontSize: "1rem" }}>
          {t({
            ja: "広告から来たら、まずは1キャラ作って1往復会話してみてください。体験が一番早いです。",
            en: "If you came from ads, create one character and try one exchange first.",
          })}
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <Link
            to={aiChatCtaPath}
            className="btn btn-border"
            style={{
              background: "#0a3f8b",
              color: "#fff",
              borderColor: "#0a3f8b",
              fontWeight: 900,
              fontSize: "1.2rem",
              padding: "14px 22px",
              letterSpacing: "0.02em",
            }}
          >
            {t({ ja: "今すぐAIチャットで遊ぶ", en: "Start Chat Now" })}
          </Link>
          <Link to="/ai_chat/howto" className="btn btn-border" style={subCtaStyle}>
            {t({ ja: "使い方を見る", en: "View How-To" })}
          </Link>
          <Link to="/ai_chat/public" className="btn btn-border" style={subCtaStyle}>
            {t({ ja: "公開チャットを見る", en: "Browse Public Chats" })}
          </Link>
        </div>
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "14px", background: "var(--surface)", marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "強み", en: "Strengths" })}</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 10 }}>
          <div style={{ border: "1px solid #d9e7fb", borderRadius: 10, padding: "10px 12px", background: "#f8fbff" }}>
            <div style={{ fontSize: 12, color: "#3b5f8f" }}>{t({ ja: "機能1", en: "Feature 1" })}</div>
            <strong>{t({ ja: "キャラ生成ができる", en: "Character generation" })}</strong>
            <p style={{ margin: "6px 0 0", color: "#35557f" }}>
              {t({ ja: "名前・性格・見た目・関係性を設定して自分専用キャラを作成。", en: "Set name, personality, appearance, and relationship." })}
            </p>
          </div>
          <div style={{ border: "1px solid #d9e7fb", borderRadius: 10, padding: "10px 12px", background: "#f8fbff" }}>
            <div style={{ fontSize: 12, color: "#3b5f8f" }}>{t({ ja: "機能2", en: "Feature 2" })}</div>
            <strong>{t({ ja: "18禁チャットができる", en: "R18 chat mode" })}</strong>
            <p style={{ margin: "6px 0 0", color: "#35557f" }}>
              {t({ ja: "R18設定を有効化して、表現範囲を広げた会話モードを利用可能。", en: "Enable R18 mode for broader expression in chat." })}
            </p>
          </div>
          <div style={{ border: "1px solid #d9e7fb", borderRadius: 10, padding: "10px 12px", background: "#f8fbff" }}>
            <div style={{ fontSize: 12, color: "#3b5f8f" }}>{t({ ja: "機能3", en: "Feature 3" })}</div>
            <strong>{t({ ja: "会話をAI小説に変換できる", en: "Convert chat to AI novel" })}</strong>
            <p style={{ margin: "6px 0 0", color: "#35557f" }}>
              {t({ ja: "会話ログからそのまま小説化して、執筆の下書きに活用。", en: "Turn chat logs into AI novel drafts directly." })}
            </p>
          </div>
        </div>
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "14px", background: "var(--surface)", marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "こんな人におすすめ", en: "Recommended for" })}</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
          <div style={{ border: "1px solid #d9e7fb", borderRadius: 10, padding: "10px 12px", background: "#fbfdff" }}>
            <strong>{t({ ja: "推しと自然に会話したい", en: "Want natural fan chats" })}</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: "0.95rem" }}>
              {t({ ja: "二次創作モードと性格設定変更で、会話の空気感を合わせやすいです。", en: "Fan mode and personality edits help match tone." })}
            </p>
          </div>
          <div style={{ border: "1px solid #d9e7fb", borderRadius: 10, padding: "10px 12px", background: "#fbfdff" }}>
            <strong>{t({ ja: "創作のネタを増やしたい", en: "Need writing inspiration" })}</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: "0.95rem" }}>
              {t({ ja: "会話からセリフや展開案を作り、そのままAI小説化できます。", en: "Generate dialogue ideas and convert to AI novel." })}
            </p>
          </div>
          <div style={{ border: "1px solid #d9e7fb", borderRadius: 10, padding: "10px 12px", background: "#fbfdff" }}>
            <strong>{t({ ja: "夜に没入して遊びたい", en: "Want immersive night sessions" })}</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: "0.95rem" }}>
              {t({ ja: "口調設定やR18設定で、好みの会話モードに寄せて遊べます。", en: "Tone and R18 settings let you personalize mode." })}
            </p>
          </div>
        </div>
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "14px", background: "var(--surface)", marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "使い方（最短3ステップ）", en: "How to use (3 steps)" })}</h3>
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8, fontSize: "0.96rem" }}>
          <li>{t({ ja: "キャラ登録: 名前・作品情報（必要なら二次創作モード）を入力して登録。", en: "Character registration: Enter name and work info (fan mode if needed)." })}</li>
          <li>{t({ ja: "性格設定変更: 性格設定を読み込み、好みに合わせて編集して反映。", en: "Edit personality settings and apply your preferred tone." })}</li>
          <li>{t({ ja: "チャット開始: 口調設定やR18設定を調整して会話を開始。", en: "Start chat after setting tone and R18 options." })}</li>
        </ol>
        <div style={{ marginTop: 10 }}>
          <Link
            to={aiChatCtaPath}
            className="btn btn-border"
            style={{
              marginRight: 8,
              background: "#0a3f8b",
              color: "#fff",
              borderColor: "#0a3f8b",
              fontWeight: 900,
              fontSize: "1.14rem",
              padding: "12px 18px",
            }}
          >
            {t({ ja: "3ステップで始める", en: "Start in 3 Steps" })}
          </Link>
          <Link to="/ai_chat/howto" className="btn btn-border">
            {t({ ja: "詳しい使い方ページへ", en: "Open detailed guide" })}
          </Link>
        </div>
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "14px", background: "var(--surface)", marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "AIチャットでできること", en: "What you can do" })}</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 10 }}>
          <div style={{ border: "1px solid #e6edf8", borderRadius: 10, padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "#5d6d86" }}>01</div>
            <strong>{t({ ja: "キャラを複数作る", en: "Create multiple characters" })}</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: "0.95rem" }}>
              {t({ ja: "1人だけでなく、複数キャラを作成して会話の幅を広げられます。", en: "Build multiple characters to expand conversations." })}
            </p>
          </div>
          <div style={{ border: "1px solid #e6edf8", borderRadius: 10, padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "#5d6d86" }}>02</div>
            <strong>{t({ ja: "関係性を入れて会話の深度を上げる", en: "Add relationships for depth" })}</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: "0.95rem" }}>
              {t({ ja: "「恋人」「相棒」など関係性を設定し、返答の一貫性を高めます。", en: "Set relationship labels like partner or teammate." })}
            </p>
          </div>
          <div style={{ border: "1px solid #e6edf8", borderRadius: 10, padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "#5d6d86" }}>03</div>
            <strong>{t({ ja: "公開チャットで人気設定を研究", en: "Study popular public chats" })}</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: "0.95rem" }}>
              {t({ ja: "公開チャット検索から他ユーザーの構成を見て参考にできます。", en: "Browse public chats for setup inspiration." })}
            </p>
          </div>
          <div style={{ border: "1px solid #e6edf8", borderRadius: 10, padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "#5d6d86" }}>04</div>
            <strong>{t({ ja: "会話をそのまま作品化", en: "Convert chats into stories" })}</strong>
            <p style={{ margin: "6px 0 0", color: "var(--muted-text)", fontSize: "0.95rem" }}>
              {t({ ja: "会話ログをAI小説に変換して、公開前の草稿に使えます。", en: "Convert chat logs into drafts before publishing." })}
            </p>
          </div>
        </div>
        <div style={{ marginTop: 12 }}>
          <Link
            to={aiChatCtaPath}
            className="btn btn-border"
            style={{ background: "#0a3f8b", color: "#fff", borderColor: "#0a3f8b", fontWeight: 900, fontSize: "1.08rem", padding: "12px 20px" }}
          >
            {t({ ja: "できることを試してみる", en: "Try these features" })}
          </Link>
        </div>
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "14px", background: "var(--surface)" }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "用語", en: "Terms" })}</h3>
        <div style={{ display: "grid", gap: 10 }}>
          <div>
            <strong>{t({ ja: "キャラ登録", en: "Character registration" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({ ja: "チャットするキャラクターを作成して保存する操作。", en: "Create and save a chat character." })}
            </p>
          </div>
          <div>
            <strong>{t({ ja: "性格設定変更", en: "Personality setting update" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({ ja: "話し方・性格・振る舞いを調整して、応答スタイルを変える機能。", en: "Adjust speech style and behavior in responses." })}
            </p>
          </div>
          <div>
            <strong>{t({ ja: "二次創作モード", en: "Fan-work mode" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({ ja: "既存作品キャラ向けの補助設定を有効にするモード。", en: "Mode for setting up existing work characters." })}
            </p>
          </div>
          <div>
            <strong>{t({ ja: "R18設定", en: "R18 setting" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({ ja: "年齢確認後に有効化できる、成人向け表現を含む設定。", en: "Adult-expression setting available after age confirmation." })}
            </p>
          </div>
        </div>
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "14px", background: "var(--surface)", marginTop: 12 }}>
        <h3 style={{ marginTop: 0 }}>{t({ ja: "よくある質問", en: "FAQ" })}</h3>
        <div style={{ display: "grid", gap: 10 }}>
          <div>
            <strong>{t({ ja: "最初に何を設定すればいい？", en: "What should I set first?" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({ ja: "まずはキャラ登録して1往復会話。必要に応じて性格設定変更を行うのが最短です。", en: "Register one character and do one exchange first." })}
            </p>
          </div>
          <div>
            <strong>{t({ ja: "二次創作キャラでも使える？", en: "Can I use fan-work characters?" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({ ja: "使えます。二次創作モードをオンにして作品情報を入れてください。", en: "Yes. Turn on fan-work mode and enter the work info." })}
            </p>
          </div>
          <div>
            <strong>{t({ ja: "R18設定はどこで使う？", en: "Where is R18 setting used?" })}</strong>
            <p style={{ margin: "4px 0 0", color: "var(--muted-text)" }}>
              {t({ ja: "チャット開始前にR18設定を有効化して利用します。年齢確認が必要です。", en: "Enable R18 setting before chat (age confirmation required)." })}
            </p>
          </div>
        </div>
      </section>

      <section
        style={{
          marginTop: 14,
          border: "1px solid #bfd8f8",
          borderRadius: 14,
          padding: "18px 14px",
          background: "linear-gradient(135deg, #eef5ff 0%, #f7faff 100%)",
          textAlign: "center",
        }}
      >
        <h3 style={{ margin: "0 0 8px" }}>{t({ ja: "迷ったらここから開始", en: "Start here" })}</h3>
        <p style={{ margin: "0 0 12px", color: "#315882" }}>
          {t({
            ja: "キャラ登録と性格設定変更だけで、すぐに会話を始められます。",
            en: "Register a character and update personality to begin chatting immediately.",
          })}
        </p>
        <Link
          to={aiChatCtaPath}
          className="btn btn-border"
          style={{
            background: "#0a3f8b",
            color: "#fff",
            borderColor: "#0a3f8b",
            fontWeight: 900,
            fontSize: "1.22rem",
            padding: "14px 26px",
            letterSpacing: "0.02em",
          }}
        >
          {t({ ja: "AIチャットページへ移動", en: "Go to AI Chat Page" })}
        </Link>
      </section>
    </div>
  );
}
