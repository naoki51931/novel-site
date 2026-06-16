import { Link, useLocation } from "react-router-dom";

export default function AiChatHowToPage() {
  const location = useLocation();
  const aiChatBasePath = location.pathname.startsWith("/en/") ? "/en/ai_chat" : "/ai_chat";

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <Link to={aiChatBasePath} className="btn btn-border">AIチャットへ戻る</Link>
        <Link to={`${aiChatBasePath}/public`} className="btn btn-border">公開チャット検索</Link>
      </div>

      <h2>AIチャットの使い方</h2>
      <p style={{ color: "#555", marginTop: 0 }}>
        アニメキャラと会話する場合の設定手順を、順番どおりにまとめています。
      </p>

      <section style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, marginBottom: 12, background: "#fcfcfd" }}>
        <h3 style={{ marginTop: 0 }}>1. 二次創作モードをオンにする</h3>
        <p style={{ marginBottom: 0 }}>
          まず「二次創作モード」をオンにしてください。アニメキャラで会話する場合は最初にここが重要です。
        </p>
      </section>

      <section style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, marginBottom: 12, background: "#fcfcfd" }}>
        <h3 style={{ marginTop: 0 }}>2. キャラ名と作品候補を設定する</h3>
        <p style={{ marginBottom: 8 }}>
          キャラ名を入力し、作品候補を選択します。アニメタイトルを入力した場合は次を行ってください。
        </p>
        <ol style={{ marginTop: 0 }}>
          <li>性格設定をいったん削除する</li>
          <li>「キャラ登録」を押す</li>
        </ol>
      </section>

      <section style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, marginBottom: 12, background: "#fcfcfd" }}>
        <h3 style={{ marginTop: 0 }}>3. 性格設定を読み込み、調整する</h3>
        <p style={{ marginBottom: 8 }}>
          「性格設定を読み込み」を押し、好きな性格や設定を性格設定欄に入れてください。
        </p>
        <p style={{ marginBottom: 8 }}>
          元の性格のほうがよい場合は、「二次創作モード補完」の文章を削除して調整できます。
        </p>
        <p style={{ marginBottom: 0 }}>
          性格設定を変更したら「性格設定を変更」ボタンを押してください。
        </p>
      </section>

      <section style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, marginBottom: 12, background: "#fcfcfd" }}>
        <h3 style={{ marginTop: 0 }}>4. キャラを増やす・関係性を入れる</h3>
        <p style={{ marginBottom: 8 }}>
          必要であればキャラを複製したり、別キャラを追加できます。
        </p>
        <p style={{ marginBottom: 6 }}>関係性の入力を忘れないでください。例:</p>
        <ul style={{ marginTop: 0, marginBottom: 0 }}>
          <li>自分同士</li>
          <li>ラブラブな恋人</li>
        </ul>
      </section>

      <section style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, marginBottom: 12, background: "#fcfcfd" }}>
        <h3 style={{ marginTop: 0 }}>5. チャット開始</h3>
        <p style={{ marginBottom: 8 }}>
          これでチャットできます。必要に応じて、口調設定やR18設定も有効にしてください。
        </p>
        <p style={{ marginBottom: 0 }}>あとはチャットをお楽しみください。</p>
      </section>
    </div>
  );
}
