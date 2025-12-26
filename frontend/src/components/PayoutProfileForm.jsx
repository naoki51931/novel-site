import { useState } from "react";
import { apiFetch } from "../lib/api";

export default function PayoutProfileForm() {
  const [form, setForm] = useState({
    bank_name: "",
    bank_branch: "",
    bank_account_type: "ordinary",
    bank_account_number: "",
    bank_account_holder: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      setSuccess("");
      await apiFetch("/api/authors/me/payout_profile", {
        method: "POST",
        body: form,
        auth: true,
      });
      setSuccess("保存しました");
    } catch (e2) {
      setError(e2.message || "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        border: "1px solid #ddd",
        borderRadius: 10,
        padding: 16,
        background: "#fff",
      }}
    >
      <h3 style={{ marginTop: 0 }}>精算設定 (銀行口座)</h3>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {success && <p style={{ color: "#0a0" }}>{success}</p>}

      <div style={{ display: "grid", gap: 10 }}>
        <label>
          銀行名
          <input
            type="text"
            value={form.bank_name}
            onChange={(e) => handleChange("bank_name", e.target.value)}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          支店名
          <input
            type="text"
            value={form.bank_branch}
            onChange={(e) => handleChange("bank_branch", e.target.value)}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          口座種別
          <select
            value={form.bank_account_type}
            onChange={(e) => handleChange("bank_account_type", e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="ordinary">普通</option>
            <option value="current">当座</option>
          </select>
        </label>

        <label>
          口座番号
          <input
            type="text"
            value={form.bank_account_number}
            onChange={(e) => handleChange("bank_account_number", e.target.value)}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          口座名義 (カナ)
          <input
            type="text"
            value={form.bank_account_holder}
            onChange={(e) => handleChange("bank_account_holder", e.target.value)}
            style={{ width: "100%" }}
          />
        </label>
      </div>

      <button
        type="submit"
        className="btn btn-border"
        disabled={saving}
        style={{ marginTop: 12 }}
      >
        {saving ? "保存中..." : "保存"}
      </button>
    </form>
  );
}
