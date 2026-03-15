/**
 * OAuth callback for Hub SSO.
 * Receives an authorization code from Hub, sends it to Entity's backend
 * which exchanges it server-side (BFF pattern — client_secret never touches the frontend).
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../shared/store";

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { fetchUser } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setError("Código de autorização ausente");
      return;
    }

    // Validate state parameter (CSRF protection)
    const expectedState = sessionStorage.getItem("oauth_state");
    const receivedState = searchParams.get("state") || "";
    if (!expectedState || expectedState !== receivedState) {
      setError("Parâmetro state inválido — possível ataque CSRF");
      return;
    }
    sessionStorage.removeItem("oauth_state");

    (async () => {
      try {
        // Send code to Entity backend (BFF) — secret stays server-side
        const exchangeRes = await fetch("/api/auth/oauth-exchange", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code,
            redirect_uri: `${window.location.origin}/auth/callback`,
          }),
        });

        if (!exchangeRes.ok) {
          const err = await exchangeRes.json().catch(() => ({}));
          throw new Error(err.detail || "Falha ao autenticar");
        }

        // Fetch user and redirect
        await fetchUser();
        navigate("/dashboard", { replace: true });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro ao autenticar");
      }
    })();
  }, [searchParams, fetchUser, navigate]);

  if (error) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
        <div className="glass-strong" style={{ padding: "2rem", maxWidth: 400, textAlign: "center" }}>
          <p style={{ color: "#fca5a5", marginBottom: "1rem" }}>{error}</p>
          <button className="btn btn-primary" onClick={() => navigate("/login")}>
            Voltar ao login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="glass" style={{ padding: "2rem 3rem" }}>
        <p style={{ color: "#fff" }}>Autenticando...</p>
      </div>
    </div>
  );
}
