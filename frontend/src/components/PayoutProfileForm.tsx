import { useState } from "react";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

type PayoutForm = {
  bank_name: string;
  bank_branch: string;
  bank_account_type: string;
  bank_account_number: string;
  bank_account_holder: string;
};

export default function PayoutProfileForm() {
  const { t } = useI18n();
  const [form, setForm] = useState<PayoutForm>({
    bank_name: "",
    bank_branch: "",
    bank_account_type: "ordinary",
    bank_account_number: "",
    bank_account_holder: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleChange = (key: keyof PayoutForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
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
      setSuccess(t({ ja: "保存しました", en: "Saved." }));
    } catch (e2) {
      setError(getErrorMessage(e2, t({ ja: "保存に失敗しました", en: "Failed to save." })));
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
      <h3 style={{ marginTop: 0 }}>
        {t({ ja: "精算設定 (銀行口座)", en: "Payout Settings (Bank Account)" })}
      </h3>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {success && <p style={{ color: "#0a0" }}>{success}</p>}

      <div style={{ display: "grid", gap: 10 }}>
        <label>
          {t({ ja: "銀行名", en: "Bank name" })}
          <input
            type="text"
            value={form.bank_name}
            onChange={(e) => handleChange("bank_name", e.target.value)}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          {t({ ja: "支店名", en: "Branch name" })}
          <input
            type="text"
            value={form.bank_branch}
            onChange={(e) => handleChange("bank_branch", e.target.value)}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          {t({ ja: "口座種別", en: "Account type" })}
          <select
            value={form.bank_account_type}
            onChange={(e) => handleChange("bank_account_type", e.target.value)}
            style={{ width: "100%" }}
          >
            <option value="ordinary">{t({ ja: "普通", en: "Savings" })}</option>
            <option value="current">{t({ ja: "当座", en: "Checking" })}</option>
          </select>
        </label>

        <label>
          {t({ ja: "口座番号", en: "Account number" })}
          <input
            type="text"
            value={form.bank_account_number}
            onChange={(e) => handleChange("bank_account_number", e.target.value)}
            style={{ width: "100%" }}
          />
        </label>

        <label>
          {t({ ja: "口座名義 (カナ)", en: "Account holder (Kana)" })}
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
        {saving ? t({ ja: "保存中...", en: "Saving..." }) : t({ ja: "保存", en: "Save" })}
      </button>
    </form>
  );
}
