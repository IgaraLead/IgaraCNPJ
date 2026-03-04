import React, { useState, useEffect } from "react";
import { useNavigate, Link, Navigate } from "react-router-dom";
import { useAuth } from "../../shared/store";

export default function RegisterPage() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [telefone, setTelefone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register, user, loading: authLoading, fetchUser } = useAuth();
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
      await register(nome, email, senha, telefone || undefined);
      navigate("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao criar conta");
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
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, textAlign: "center", marginBottom: "0.5rem" }}>
          <span style={{ background: "linear-gradient(135deg, hsl(268,100%,60%), hsl(213,100%,60%))", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Criar Conta</span>
        </h1>
        <p style={{ color: "rgba(255,255,255,0.45)", textAlign: "center", fontSize: "0.875rem", marginBottom: "2rem" }}>
          Crie sua conta gratuitamente
        </p>

        {error && (
          <div style={{ background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, padding: "0.75rem", marginBottom: "1rem", color: "#fca5a5", fontSize: "0.875rem" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div>
            <label style={{ display: "block", color: "rgba(255,255,255,0.8)", fontSize: "0.875rem", marginBottom: "0.375rem" }}>Nome</label>
            <input className="input" type="text" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Seu nome" required />
          </div>
          <div>
            <label style={{ display: "block", color: "rgba(255,255,255,0.8)", fontSize: "0.875rem", marginBottom: "0.375rem" }}>Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seu@email.com" required />
          </div>
          <div>
            <label style={{ display: "block", color: "rgba(255,255,255,0.8)", fontSize: "0.875rem", marginBottom: "0.375rem" }}>Senha</label>
            <input className="input" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} placeholder="Mínimo 8 caracteres" required minLength={8} />
          </div>
          <div>
            <label style={{ display: "block", color: "rgba(255,255,255,0.8)", fontSize: "0.875rem", marginBottom: "0.375rem" }}>Telefone (opcional)</label>
            <input className="input" type="tel" value={telefone} onChange={(e) => setTelefone(e.target.value)} placeholder="11999999999" />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center", padding: "0.75rem" }}>
            {loading ? "Criando..." : "Criar Conta"}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: "1.5rem", color: "rgba(255,255,255,0.6)", fontSize: "0.875rem" }}>
          Já tem conta?{" "}
          <Link to="/login" style={{ color: "hsl(213,100%,60%)", textDecoration: "none", fontWeight: 500 }}>Entrar</Link>
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
