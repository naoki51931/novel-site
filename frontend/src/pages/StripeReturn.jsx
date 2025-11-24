import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function StripeReturn({ mode }) {
  const navigate = useNavigate();

  useEffect(() => {
    const returnTo = sessionStorage.getItem("stripe_return_to") || "/";
    sessionStorage.removeItem("stripe_return_to");
    navigate(returnTo, { replace: true });
  }, [navigate]);

  return (
    <div>
      <p>
        {mode === "cancel"
          ? "決済をキャンセルしました。元のページに戻ります..."
          : "決済が完了しました。元のページに戻ります..."}
      </p>
    </div>
  );
}
