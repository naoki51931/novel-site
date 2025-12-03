import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function AccountSettings() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { navigate("/login"); return; }

    fetch(`/api/users/me`, {
      headers: { Authorization: "Bearer " + token }
    })
      .then(res => res.json())
      .then(data => {
        setEmail(data.email || "");
        setBirthDate(data.birth_date || "");
      })
      .catch((e) => setError(e.message || "プロフィール取得に失敗しました"))
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const token = localStorage.getItem("token");
      if (!token) throw new Error("ログインが必要です。");

      const res = await fetch(`/api/users/me`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({
          email,
          birth_date: birthDate,
        }),
      });

      let msg = "保存しました。";
      if (!res.ok) {
        try {
          const d = await res.json();
          if (d && d.detail) msg = d.detail;
        } catch (_) {
          msg = `保存に失敗しました (HTTP ${res.status})`;
        }
        throw new Error(msg);
      }

      alert("保存しました。");
    } catch (e) {
      setError(e.message || "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>読み込み中...</p>;

  return (
    <div>
      <h2>マイページ設定</h2>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 8 }}>
          <label>
            メールアドレス<br />
            <input
              type="email"
              value={email}
              onChange={(e)=>setEmail(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: 8 }}>
          <label>
            生年月日<br />
            <input
              type="date"
              value={birthDate}
              onChange={(e)=>setBirthDate(e.target.value)}
              style={{ width:"100%", padding:4 }}
            />
          </label>
        </div>

        {error && <p style={{ color:"red" }}>{error}</p>}

        <button className="btn btn-border" type="submit" disabled={saving}>
          {saving ? "保存中..." : "保存する"}
        </button>
      </form>
    </div>
  );
}
