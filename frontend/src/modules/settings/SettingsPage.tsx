import React, { useState } from "react";
import { useAuth } from "../../shared/store";
import { authApi } from "../../shared/api";

export default function SettingsPage() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordMsg(null);

    if (newPassword.length < 8) {
      setPasswordMsg({ ok: false, text: "Nova senha deve ter no mínimo 8 caracteres." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ ok: false, text: "As senhas não coincidem." });
      return;
    }

    setSaving(true);
    try {
      await authApi.changePassword({ senha_atual: currentPassword, nova_senha: newPassword });
      setPasswordMsg({ ok: true, text: "Senha alterada com sucesso!" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      setPasswordMsg({ ok: false, text: err instanceof Error ? err.message : "Erro ao alterar senha" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page animate-in">
      <h1 className="page-title">Configurações</h1>

      {/* Profile info (read-only) */}
      <div className="glass-strong" style={{ padding: "1.5rem", maxWidth: 500, marginBottom: "1.5rem" }}>
        <h2 style={{ color: "#fff", fontSize: "1.125rem", fontWeight: 600, marginBottom: "1.5rem" }}>
          Perfil
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div>
            <label style={labelStyle}>Nome</label>
            <input className="input" value={user?.nome ?? ""} readOnly />
          </div>
          <div>
            <label style={labelStyle}>Email</label>
            <input className="input" value={user?.email ?? ""} readOnly />
          </div>
          <div>
            <label style={labelStyle}>Plano</label>
            <input className="input" value={user?.plano || "Gratuito"} readOnly style={{ textTransform: "capitalize" }} />
          </div>
          <div>
            <label style={labelStyle}>Status Assinatura</label>
            <input className="input" value={user?.status_assinatura || "—"} readOnly />
          </div>
        </div>
      </div>

      {/* Password change form */}
      <div className="glass-strong" style={{ padding: "1.5rem", maxWidth: 500 }}>
        <h2 style={{ color: "#fff", fontSize: "1.125rem", fontWeight: 600, marginBottom: "1.5rem" }}>
          Alterar Senha
        </h2>
        <form onSubmit={handlePasswordChange} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div>
            <label style={labelStyle}>Senha atual</label>
            <input
              className="input"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label style={labelStyle}>Nova senha</label>
            <input
              className="input"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
          <div>
            <label style={labelStyle}>Confirmar nova senha</label>
            <input
              className="input"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          {passwordMsg && (
            <p style={{ color: passwordMsg.ok ? "#86efac" : "#fca5a5", fontSize: "0.875rem" }}>
              {passwordMsg.text}
            </p>
          )}
          <button className="btn btn-primary" type="submit" disabled={saving} style={{ alignSelf: "flex-start" }}>
            {saving ? "Salvando..." : "Salvar Senha"}
          </button>
        </form>
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  color: "rgba(255,255,255,0.7)",
  fontSize: "0.8rem",
  marginBottom: "0.375rem",
};
