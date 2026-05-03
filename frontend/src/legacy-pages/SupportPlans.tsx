import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

const DEFAULT_CREATE = {
  name: "",
  amount_yen: 300,
  stripe_price_id: "",
};

type SupportPlan = {
  id: number | string;
  name?: string | null;
  amount_yen: number;
  stripe_price_id: string;
  is_active?: boolean | null;
};

type SupportPlanForm = {
  name: string;
  amount_yen: number | string;
  stripe_price_id: string;
};

export default function SupportPlans() {
  const { t } = useI18n();
  const [plans, setPlans] = useState<SupportPlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [createForm, setCreateForm] = useState<SupportPlanForm>(DEFAULT_CREATE);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState<SupportPlan["id"] | null>(null);
  const [editForm, setEditForm] = useState<SupportPlanForm | null>(null);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await apiFetch("/api/authors/me/support_plans", { auth: true });
      setPlans(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "プランの取得に失敗しました", en: "Failed to load plans." })));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, []);

  const handleCreate = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const amount = Number(createForm.amount_yen);
    if (!Number.isFinite(amount) || amount < 100 || amount > 100000 || amount % 100 !== 0) {
      setError(
        t({ ja: "月額は100〜100000の100円刻みで入力してください", en: "Monthly amount must be 100–100000 in 100 JPY steps." })
      );
      return;
    }
    if (!createForm.stripe_price_id.trim()) {
      setError(t({ ja: "stripe_price_id は必須です", en: "stripe_price_id is required." }));
      return;
    }
    try {
      setSaving(true);
      setError("");
      await apiFetch("/api/authors/me/support_plans", {
        method: "POST",
        body: {
          name: createForm.name?.trim() || null,
          amount_yen: amount,
          stripe_price_id: createForm.stripe_price_id.trim(),
        },
        auth: true,
      });
      setCreateForm(DEFAULT_CREATE);
      await fetchPlans();
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "プランの作成に失敗しました", en: "Failed to create plan." })));
    } finally {
      setSaving(false);
    }
  };

  const beginEdit = (plan: SupportPlan) => {
    setEditId(plan.id);
    setEditForm({
      name: plan.name || "",
      amount_yen: plan.amount_yen,
      stripe_price_id: plan.stripe_price_id || "",
    });
  };

  const cancelEdit = () => {
    setEditId(null);
    setEditForm(null);
  };

  const handleUpdate = async () => {
    if (!editForm || !editId) return;
    const amount = Number(editForm.amount_yen);
    if (!Number.isFinite(amount) || amount < 100 || amount > 100000 || amount % 100 !== 0) {
      setError(
        t({ ja: "月額は100〜100000の100円刻みで入力してください", en: "Monthly amount must be 100–100000 in 100 JPY steps." })
      );
      return;
    }
    if (!editForm.stripe_price_id.trim()) {
      setError(t({ ja: "stripe_price_id は必須です", en: "stripe_price_id is required." }));
      return;
    }
    try {
      setSaving(true);
      setError("");
      await apiFetch(`/api/authors/me/support_plans/${editId}`, {
        method: "PATCH",
        body: {
          name: editForm.name?.trim() || null,
          amount_yen: amount,
          stripe_price_id: editForm.stripe_price_id.trim(),
        },
        auth: true,
      });
      cancelEdit();
      await fetchPlans();
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "プランの更新に失敗しました", en: "Failed to update plan." })));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (plan: SupportPlan, toActive: boolean) => {
    const action = toActive ? "activate" : "deactivate";
    const label = toActive ? t({ ja: "有効化", en: "Activate" }) : t({ ja: "無効化", en: "Deactivate" });
    if (!window.confirm(t({ ja: "{{label}}しますか？", en: "{{label}} this plan?" }, { label }))) return;
    try {
      setSaving(true);
      setError("");
      await apiFetch(`/api/authors/me/support_plans/${plan.id}/${action}`, {
        method: "POST",
        auth: true,
      });
      await fetchPlans();
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "{{label}}に失敗しました", en: "{{label}} failed." }, { label })));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/me/creator">
          {t({ ja: "← 作者ダッシュボードへ戻る", en: "← Back to Creator Dashboard" })}
        </Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>
        {t({ ja: "月額支援プラン管理", en: "Monthly Support Plans" })}
      </h2>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 16,
          background: "#fff",
          marginBottom: 16,
        }}
      >
        <h3 style={{ marginTop: 0 }}>{t({ ja: "新規作成", en: "Create new" })}</h3>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <div style={{ fontSize: 12, color: "#666", marginBottom: 10 }}>
          {t({
            ja: "stripe_price_id は Stripe で作成した Price ID を入力してください。価格を変更する場合は Stripe で新しい Price を作成し、ここで更新します。",
            en: "Enter the Price ID created in Stripe. If you change the price, create a new Price in Stripe and update it here.",
          })}
        </div>
        <div style={{ marginBottom: 10 }}>
          <Link className="btn btn-border" to="/me/support-plans/manual">
            {t({ ja: "stripe_price_id マニュアルを見る", en: "View stripe_price_id guide" })}
          </Link>
        </div>
        <form onSubmit={handleCreate} style={{ display: "grid", gap: 10 }}>
          <label>
            {t({ ja: "プラン名 (任意)", en: "Plan name (optional)" })}
            <input
              type="text"
              value={createForm.name}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, name: e.target.value }))
              }
              placeholder={t({ ja: "月額300", en: "Monthly 300" })}
              style={{ width: "100%" }}
            />
          </label>
          <label>
            {t({ ja: "月額 (円)", en: "Monthly (JPY)" })}
            <input
              type="number"
              min={100}
              max={100000}
              step={100}
              value={createForm.amount_yen}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, amount_yen: Number(e.target.value) }))
              }
              style={{ width: "100%" }}
            />
          </label>
          <label>
            {t({ ja: "stripe_price_id (必須)", en: "stripe_price_id (required)" })}
            <input
              type="text"
              value={createForm.stripe_price_id}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, stripe_price_id: e.target.value }))
              }
              placeholder="price_..."
              style={{ width: "100%" }}
            />
          </label>
          <button type="submit" className="btn btn-border" disabled={saving}>
            {saving ? t({ ja: "作成中...", en: "Creating..." }) : t({ ja: "作成", en: "Create" })}
          </button>
        </form>
      </section>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 16,
          background: "#fff",
        }}
      >
        <h3 style={{ marginTop: 0 }}>{t({ ja: "登録済みプラン", en: "Existing plans" })}</h3>
        {loading ? (
          <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
        ) : plans.length === 0 ? (
          <p>{t({ ja: "プランがありません。", en: "No plans yet." })}</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  {t({ ja: "名前", en: "Name" })}
                </th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  {t({ ja: "月額", en: "Monthly" })}
                </th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  {t({ ja: "状態", en: "Status" })}
                </th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  stripe_price_id
                </th>
                <th style={{ borderBottom: "1px solid #eee" }}>
                  {t({ ja: "操作", en: "Actions" })}
                </th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan: SupportPlan) => {
                const isEditing = editId === plan.id;
                return (
                  <tr key={plan.id}>
                    <td style={{ padding: "8px 4px" }}>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editForm?.name ?? ""}
                          onChange={(e) =>
                            setEditForm((prev) => (prev ? { ...prev, name: e.target.value } : prev))
                          }
                        />
                      ) : (
                        plan.name
                      )}
                    </td>
                    <td style={{ padding: "8px 4px" }}>
                      {isEditing ? (
                        <input
                          type="number"
                          min={100}
                          max={100000}
                          step={100}
                          value={editForm?.amount_yen ?? ""}
                          onChange={(e) =>
                            setEditForm((prev) =>
                              prev
                                ? {
                                    ...prev,
                                    amount_yen: e.target.value,
                                  }
                                : prev
                            )
                          }
                        />
                      ) : (
                        t({ ja: "{{amount}}円", en: "¥{{amount}}" }, { amount: plan.amount_yen })
                      )}
                    </td>
                    <td style={{ padding: "8px 4px" }}>
                      {plan.is_active
                        ? t({ ja: "active", en: "Active" })
                        : t({ ja: "inactive", en: "Inactive" })}
                    </td>
                    <td style={{ padding: "8px 4px" }}>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editForm?.stripe_price_id ?? ""}
                          onChange={(e) =>
                            setEditForm((prev) =>
                              prev
                                ? {
                                    ...prev,
                                    stripe_price_id: e.target.value,
                                  }
                                : prev
                            )
                          }
                        />
                      ) : (
                        <span style={{ fontSize: 12 }}>{plan.stripe_price_id}</span>
                      )}
                    </td>
                    <td style={{ padding: "8px 4px", whiteSpace: "nowrap" }}>
                      {isEditing ? (
                        <>
                          <button
                            type="button"
                            className="btn btn-border"
                            onClick={handleUpdate}
                            disabled={saving}
                          >
                            {t({ ja: "保存", en: "Save" })}
                          </button>
                          <button
                            type="button"
                            className="btn btn-border"
                            onClick={cancelEdit}
                            disabled={saving}
                            style={{ marginLeft: 6 }}
                          >
                            {t({ ja: "取消", en: "Cancel" })}
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="btn btn-border"
                            onClick={() => beginEdit(plan)}
                          >
                            {t({ ja: "編集", en: "Edit" })}
                          </button>
                          {plan.is_active ? (
                            <button
                              type="button"
                              className="btn btn-border"
                              onClick={() => handleToggleActive(plan, false)}
                              style={{ marginLeft: 6 }}
                              disabled={saving}
                            >
                              {t({ ja: "無効化", en: "Deactivate" })}
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-border"
                              onClick={() => handleToggleActive(plan, true)}
                              style={{ marginLeft: 6 }}
                              disabled={saving}
                            >
                              {t({ ja: "有効化", en: "Activate" })}
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <p style={{ marginTop: 12, fontSize: 12, color: "#666" }}>
          {t({
            ja: "プラン無効化は新規支援の受付停止です。既存の購読は別途管理してください。",
            en: "Deactivating a plan stops new support. Manage existing subscriptions separately.",
          })}
        </p>
      </section>
    </div>
  );
}
