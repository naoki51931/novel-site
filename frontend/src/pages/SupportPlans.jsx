import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

const DEFAULT_CREATE = {
  name: "",
  amount_yen: 300,
  stripe_price_id: "",
};

export default function SupportPlans() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [createForm, setCreateForm] = useState(DEFAULT_CREATE);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState(null);
  const [editForm, setEditForm] = useState(null);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await apiFetch("/api/authors/me/support_plans", { auth: true });
      setPlans(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || "プランの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    const amount = Number(createForm.amount_yen);
    if (!Number.isFinite(amount) || amount < 100 || amount > 100000 || amount % 100 !== 0) {
      setError("月額は100〜100000の100円刻みで入力してください");
      return;
    }
    if (!createForm.stripe_price_id.trim()) {
      setError("stripe_price_id は必須です");
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
      setError(e.message || "プランの作成に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const beginEdit = (plan) => {
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
      setError("月額は100〜100000の100円刻みで入力してください");
      return;
    }
    if (!editForm.stripe_price_id.trim()) {
      setError("stripe_price_id は必須です");
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
      setError(e.message || "プランの更新に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (plan, toActive) => {
    const action = toActive ? "activate" : "deactivate";
    const label = toActive ? "有効化" : "無効化";
    if (!window.confirm(`${label}しますか？`)) return;
    try {
      setSaving(true);
      setError("");
      await apiFetch(`/api/authors/me/support_plans/${plan.id}/${action}`, {
        method: "POST",
        auth: true,
      });
      await fetchPlans();
    } catch (e) {
      setError(e.message || `${label}に失敗しました`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <div style={{ marginBottom: 12 }}>
        <Link to="/me/creator">← 作者ダッシュボードへ戻る</Link>
      </div>

      <h2 style={{ marginBottom: 16 }}>月額支援プラン管理</h2>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 16,
          background: "#fff",
          marginBottom: 16,
        }}
      >
        <h3 style={{ marginTop: 0 }}>新規作成</h3>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <div style={{ fontSize: 12, color: "#666", marginBottom: 10 }}>
          stripe_price_id は Stripe で作成した Price ID を入力してください。
          価格を変更する場合は Stripe で新しい Price を作成し、ここで更新します。
        </div>
        <div style={{ marginBottom: 10 }}>
          <Link className="btn btn-border" to="/me/support-plans/manual">
            stripe_price_id マニュアルを見る
          </Link>
        </div>
        <form onSubmit={handleCreate} style={{ display: "grid", gap: 10 }}>
          <label>
            プラン名 (任意)
            <input
              type="text"
              value={createForm.name}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, name: e.target.value }))
              }
              placeholder="月額300"
              style={{ width: "100%" }}
            />
          </label>
          <label>
            月額 (円)
            <input
              type="number"
              min={100}
              max={100000}
              step={100}
              value={createForm.amount_yen}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, amount_yen: e.target.value }))
              }
              style={{ width: "100%" }}
            />
          </label>
          <label>
            stripe_price_id (必須)
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
            {saving ? "作成中..." : "作成"}
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
        <h3 style={{ marginTop: 0 }}>登録済みプラン</h3>
        {loading ? (
          <p>読み込み中...</p>
        ) : plans.length === 0 ? (
          <p>プランがありません。</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  名前
                </th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  月額
                </th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  状態
                </th>
                <th style={{ textAlign: "left", borderBottom: "1px solid #eee" }}>
                  stripe_price_id
                </th>
                <th style={{ borderBottom: "1px solid #eee" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => {
                const isEditing = editId === plan.id;
                return (
                  <tr key={plan.id}>
                    <td style={{ padding: "8px 4px" }}>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editForm?.name ?? ""}
                          onChange={(e) =>
                            setEditForm((prev) => ({ ...prev, name: e.target.value }))
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
                            setEditForm((prev) => ({
                              ...prev,
                              amount_yen: e.target.value,
                            }))
                          }
                        />
                      ) : (
                        `${plan.amount_yen}円`
                      )}
                    </td>
                    <td style={{ padding: "8px 4px" }}>
                      {plan.is_active ? "active" : "inactive"}
                    </td>
                    <td style={{ padding: "8px 4px" }}>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editForm?.stripe_price_id ?? ""}
                          onChange={(e) =>
                            setEditForm((prev) => ({
                              ...prev,
                              stripe_price_id: e.target.value,
                            }))
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
                            保存
                          </button>
                          <button
                            type="button"
                            className="btn btn-border"
                            onClick={cancelEdit}
                            disabled={saving}
                            style={{ marginLeft: 6 }}
                          >
                            取消
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="btn btn-border"
                            onClick={() => beginEdit(plan)}
                          >
                            編集
                          </button>
                          {plan.is_active ? (
                            <button
                              type="button"
                              className="btn btn-border"
                              onClick={() => handleToggleActive(plan, false)}
                              style={{ marginLeft: 6 }}
                              disabled={saving}
                            >
                              無効化
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-border"
                              onClick={() => handleToggleActive(plan, true)}
                              style={{ marginLeft: 6 }}
                              disabled={saving}
                            >
                              有効化
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
          プラン無効化は新規支援の受付停止です。既存の購読は別途管理してください。
        </p>
      </section>
    </div>
  );
}
