import React, { useState, useEffect } from "react";
import { Link, useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "../../shared/store";
import Logo from "../../shared/ui/Logo";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, user, loading: authLoading, fetchUser } = useAuth();
  const navigate = useNavigate();

  useEffect(() => { fetchUser(); }, [fetchUser]);

  if (authLoading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="glass" style={{ padding: "2rem 3rem" }}>
          <p style={{ color: "#fff" }}>Carregando...</p>
        </div>
      </div>
    );
  }

  if (user) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, senha);
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao fazer login");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
      }}
    >
      <div className="glass-strong animate-in" style={{ padding: "2.5rem", width: "100%", maxWidth: 420 }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "1rem" }}>
          <Logo size={56} />
        </div>
        <h1 style={{ fontSize: "1.4rem", fontWeight: 700, textAlign: "center", marginBottom: "0.5rem" }}>
          <span style={{ background: "linear-gradient(135deg, hsl(268,100%,60%), hsl(213,100%,60%))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>IgaraLead Entity</span>
        </h1>
        <p style={{ color: "rgba(255,255,255,0.45)", textAlign: "center", fontSize: "0.875rem", marginBottom: "2rem" }}>
          Faça login na sua conta
        </p>

        {error && (
          <div style={{ background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, padding: "0.75rem", marginBottom: "1rem", color: "#fca5a5", fontSize: "0.875rem" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div>
            <label style={{ display: "block", color: "rgba(255,255,255,0.8)", fontSize: "0.875rem", marginBottom: "0.375rem" }}>Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seu@email.com" required />
          </div>
          <div>
            <label style={{ display: "block", color: "rgba(255,255,255,0.8)", fontSize: "0.875rem", marginBottom: "0.375rem" }}>Senha</label>
            <input className="input" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} placeholder="••••••••" required />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center", padding: "0.75rem" }}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: "1.5rem", color: "rgba(255,255,255,0.6)", fontSize: "0.875rem" }}>
          Não tem conta?{" "}
          <Link to="/register" style={{ color: "hsl(213,100%,60%)", textDecoration: "none", fontWeight: 500 }}>Criar conta</Link>
        </p>
      </div>

      <footer style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        padding: "1rem",
        textAlign: "center",
        color: "rgba(255,255,255,0.35)",
        fontSize: "0.75rem",
      }}>
        © {new Date().getFullYear()}{" "}
        <a
          href="https://igaralead.com.br"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "rgba(255,255,255,0.55)", textDecoration: "none", fontWeight: 500 }}
        >
          IgaraLead
        </a>
        . Todos os direitos reservados.
      </footer>
    </div>
  );
}
