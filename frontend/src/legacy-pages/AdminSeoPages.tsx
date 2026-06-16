import { Link, useNavigate } from "react-router-dom";
import { type FormEvent, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { getErrorMessage } from "../lib/errorUtils";
import { useI18n } from "../lib/i18n";

type AdminSeoPage = {
  id: number;
  slug: string;
  title: string;
  description?: string | null;
  h1: string;
  body: string;
  related_tags?: string[] | null;
  is_published?: boolean | null;
};

const EMPTY_FORM = {
  id: 0,
  slug: "",
  title: "",
  description: "",
  h1: "",
  body: "",
  related_tags: "",
  is_published: false,
};

export default function AdminSeoPages() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [items, setItems] = useState<AdminSeoPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);

  const load = async () => {
    try {
      setLoading(true);
      setError("");
      await apiFetch("/api/admin/auth/me", { credentials: "include" });
      const data = await apiFetch("/api/admin/seo-pages", { credentials: "include" });
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      if ((e as any)?.status === 401 || (e as any)?.status === 403) {
        navigate("/admin/login", { replace: true });
        return;
      }
      setError(getErrorMessage(e, t({ ja: "SEOページ一覧の取得に失敗しました。", en: "Failed to load SEO pages." })));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const startEdit = (item: AdminSeoPage) => {
    setForm({
      id: item.id,
      slug: item.slug || "",
      title: item.title || "",
      description: item.description || "",
      h1: item.h1 || "",
      body: item.body || "",
      related_tags: Array.isArray(item.related_tags) ? item.related_tags.join(", ") : "",
      is_published: item.is_published === true,
    });
    setMessage("");
    setError("");
  };

  const resetForm = () => setForm(EMPTY_FORM);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError("");
      setMessage("");
      const payload = {
        slug: form.slug,
        title: form.title,
        description: form.description || null,
        h1: form.h1,
        body: form.body,
        related_tags: String(form.related_tags || "")
          .split(",")
          .map((part) => part.trim())
          .filter(Boolean),
        is_published: form.is_published,
      };
      if (form.id) {
        await apiFetch(`/api/admin/seo-pages/${form.id}`, {
          method: "PUT",
          body: payload,
          credentials: "include",
        });
      } else {
        await apiFetch("/api/admin/seo-pages", {
          method: "POST",
          body: payload,
          credentials: "include",
        });
      }
      setMessage(t({ ja: "保存しました。", en: "Saved." }));
      resetForm();
      await load();
    } catch (e) {
      setError(getErrorMessage(e, t({ ja: "SEOページの保存に失敗しました。", en: "Failed to save SEO page." })));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", display: "grid", gap: 20 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <Link to="/admin" className="btn btn-border">
          {t({ ja: "← 管理画面に戻る", en: "← Back to Admin" })}
        </Link>
        <a href={form.slug ? `/seo/${encodeURIComponent(form.slug)}` : "/seo"} className="btn btn-border" target="_blank" rel="noreferrer">
          {t({ ja: "公開ページを確認", en: "Preview public page" })}
        </a>
      </div>

      <section style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 16, background: "var(--surface)" }}>
        <h2 style={{ marginTop: 0 }}>{form.id ? t({ ja: "SEOページ編集", en: "Edit SEO Page" }) : t({ ja: "SEOページ作成", en: "Create SEO Page" })}</h2>
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
          <input value={form.slug} onChange={(e) => setForm((prev) => ({ ...prev, slug: e.target.value }))} placeholder="slug" />
          <input value={form.title} onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))} placeholder="title" />
          <input value={form.description} onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))} placeholder="description" />
          <input value={form.h1} onChange={(e) => setForm((prev) => ({ ...prev, h1: e.target.value }))} placeholder="h1" />
          <textarea value={form.body} onChange={(e) => setForm((prev) => ({ ...prev, body: e.target.value }))} placeholder="body" rows={10} />
          <input value={form.related_tags} onChange={(e) => setForm((prev) => ({ ...prev, related_tags: e.target.value }))} placeholder="related tags (comma separated)" />
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={form.is_published} onChange={(e) => setForm((prev) => ({ ...prev, is_published: e.target.checked }))} />
            <span>{t({ ja: "公開する", en: "Published" })}</span>
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? t({ ja: "保存中...", en: "Saving..." }) : t({ ja: "保存", en: "Save" })}
            </button>
            <button type="button" className="btn btn-border" onClick={resetForm}>
              {t({ ja: "新規作成に戻す", en: "Reset" })}
            </button>
          </div>
        </form>
        {message ? <p style={{ color: "green", marginBottom: 0 }}>{message}</p> : null}
        {error ? <p style={{ color: "red", marginBottom: 0 }}>{error}</p> : null}
      </section>

      <section style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 16, background: "var(--surface)" }}>
        <h2 style={{ marginTop: 0 }}>{t({ ja: "SEOページ一覧", en: "SEO Pages" })}</h2>
        {loading ? (
          <p>{t({ ja: "読み込み中...", en: "Loading..." })}</p>
        ) : items.length === 0 ? (
          <p>{t({ ja: "SEOページはまだありません。", en: "No SEO pages yet." })}</p>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                className="btn btn-border"
                style={{ textAlign: "left", display: "grid", gap: 4 }}
                onClick={() => startEdit(item)}
              >
                <strong>{item.title}</strong>
                <span>/seo/{item.slug}</span>
                <span>{item.is_published ? t({ ja: "公開中", en: "Published" }) : t({ ja: "下書き", en: "Draft" })}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
