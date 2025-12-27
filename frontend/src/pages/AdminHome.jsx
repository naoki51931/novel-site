import { Link, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { apiFetch } from "../lib/api";

export default function AdminHome() {
  const navigate = useNavigate();

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
      <h2 style={{ marginBottom: 16 }}>管理画面</h2>
      <p style={{ marginBottom: 12 }}>運営向けの管理機能です。</p>
      <Link className="btn btn-border" to="/admin/payouts">
        精算管理へ
      </Link>
      <Link className="btn btn-border" to="/admin/dashboard" style={{ marginLeft: 8 }}>
        支援/振込ダッシュボードへ
      </Link>
      <button
        type="button"
        className="btn btn-border"
        onClick={handleLogout}
        style={{ marginLeft: 8 }}
      >
        ログアウト
      </button>
    </div>
  );
}
