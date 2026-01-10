import { Link, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { apiFetch } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function AdminHome() {
  const navigate = useNavigate();
  const { t } = useI18n();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        await apiFetch("/api/admin/auth/me", { credentials: "include" });
      } catch {
        navigate("/admin/login", { replace: true });
      }
    };
    checkAuth();
  }, [navigate]);

  const handleLogout = async () => {
    await apiFetch("/api/admin/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    navigate("/admin/login", { replace: true });
  };

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 16 }}>{t({ ja: "管理画面", en: "Admin" })}</h2>
      <p style={{ marginBottom: 12 }}>
        {t({ ja: "運営向けの管理機能です。", en: "Administration tools for operators." })}
      </p>
      <Link className="btn btn-border" to="/admin/payouts">
        {t({ ja: "精算管理へ", en: "Go to Payouts" })}
      </Link>
      <Link className="btn btn-border" to="/admin/dashboard" style={{ marginLeft: 8 }}>
        {t({ ja: "支援/振込ダッシュボードへ", en: "Go to Support & Payout Dashboard" })}
      </Link>
      <button
        type="button"
        className="btn btn-border"
        onClick={handleLogout}
        style={{ marginLeft: 8 }}
      >
        {t({ ja: "ログアウト", en: "Log out" })}
      </button>
    </div>
  );
}
