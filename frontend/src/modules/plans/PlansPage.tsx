import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { plansApi, type Plan } from "../../shared/api";
import { useAuth } from "../../shared/store";

export default function PlansPage() {
  const { user, fetchUser } = useAuth();
  const queryClient = useQueryClient();
  const { data: plans, isLoading } = useQuery({ queryKey: ["plans"], queryFn: plansApi.list });

  const subscribeMutation = useMutation({
    mutationFn: (plano: string) => plansApi.subscribe(plano),
    onSuccess: (data) => {
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      // Auto-activated (no PagSeguro) — just refresh user state
      fetchUser();
      queryClient.invalidateQueries({ queryKey: ["credits"] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: plansApi.cancel,
    onSuccess: () => {
      fetchUser();
      queryClient.invalidateQueries({ queryKey: ["credits"] });
    },
  });

  return (
    <div className="page animate-in">
      <h1 className="page-title">Planos</h1>

      {user?.status_assinatura === "ativa" && (
        <div className="glass-strong" style={{ padding: "1.25rem", marginBottom: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <p style={{ color: "#fff", fontWeight: 600 }}>
              Plano atual: <span style={{ textTransform: "capitalize" }}>{user.plano}</span>
            </p>
            <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>
              Créditos: {user.saldo_creditos.toLocaleString("pt-BR")}
            </p>
          </div>
          <button
            className="btn btn-danger"
            onClick={() => {
              if (confirm("Tem certeza que deseja cancelar?")) cancelMutation.mutate();
            }}
            disabled={cancelMutation.isPending}
          >
            Cancelar Assinatura
          </button>
        </div>
      )}

      {isLoading ? (
        <p style={{ color: "#fff" }}>Carregando planos...</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
          {plans?.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              isCurrent={user?.plano === plan.id}
              onSubscribe={() => subscribeMutation.mutate(plan.id)}
              loading={subscribeMutation.isPending}
              hasActiveSub={user?.status_assinatura === "ativa"}
            />
          ))}
        </div>
      )}

      {(subscribeMutation.isError || cancelMutation.isError) && (
        <div style={{ background: "rgba(239,68,68,0.15)", borderRadius: 8, padding: "1rem", marginTop: "1rem", color: "#fca5a5" }}>
          {(subscribeMutation.error || cancelMutation.error)?.message}
        </div>
      )}
    </div>
  );
}

function PlanCard({ plan, isCurrent, onSubscribe, loading, hasActiveSub }: {
  plan: Plan;
  isCurrent: boolean;
  onSubscribe: () => void;
  loading: boolean;
  hasActiveSub: boolean;
}) {
  return (
    <div
      className="glass-strong"
      style={{
        padding: "1.5rem",
        border: isCurrent ? "2px solid var(--primary)" : undefined,
        position: "relative",
      }}
    >
      {isCurrent && (
        <span className="badge badge-success" style={{ position: "absolute", top: "1rem", right: "1rem" }}>
          Atual
        </span>
      )}
      <h3 style={{ color: "#fff", fontSize: "1.25rem", fontWeight: 700, marginBottom: "0.25rem" }}>
        {plan.name}
      </h3>
      <p style={{ color: "#fff", fontSize: "2rem", fontWeight: 700, marginBottom: "0.5rem" }}>
        R$ {plan.price.toFixed(0)}
        <span style={{ fontSize: "0.875rem", fontWeight: 400, color: "rgba(255,255,255,0.5)" }}>/mês</span>
      </p>
      <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <li style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.875rem" }}>
          ✓ {plan.credits.toLocaleString("pt-BR")} créditos/mês
        </li>
        <li style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.875rem" }}>
          ✓ R$ {plan.credit_price.toFixed(3)} por crédito
        </li>
        <li style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.875rem" }}>
          ✓ Créditos acumulam (máx {plan.max_accumulation.toLocaleString("pt-BR")})
        </li>
        <li style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.875rem" }}>
          ✓ Exportação CSV/Excel
        </li>
      </ul>
      <button
        className="btn btn-primary"
        style={{ width: "100%", justifyContent: "center" }}
        onClick={onSubscribe}
        disabled={isCurrent || loading || (hasActiveSub && !isCurrent)}
      >
        {isCurrent ? "Plano Atual" : hasActiveSub ? "Cancele o atual primeiro" : "Assinar"}
      </button>
    </div>
  );
}
