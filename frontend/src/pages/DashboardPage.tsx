import React, { useCallback, useEffect, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/services/api";

const DEMO_ROLES = [
  { label: "Admin (Hosp A)", email: "admin.a@metrogeneral.org" },
  { label: "Billing Manager", email: "billing.a@metrogeneral.org" },
  { label: "Pharmacist (Priya)", email: "pharmacist.a@metrogeneral.org" },
  { label: "Pharmacist (Ravi)", email: "ravi.a@metrogeneral.org" },
  { label: "Front Desk", email: "frontdesk.a@metrogeneral.org" },
  { label: "Doctor", email: "doctor.a@metrogeneral.org" },
  { label: "Admin (Hosp B)", email: "admin.b@citycare.org" },
];

export function DashboardPage() {
  const { user, permissions, hasPermission, login } = useAuth();
  const [switchingEmail, setSwitchingEmail] = useState<string | null>(null);
  const demoLoginEnabled = import.meta.env.VITE_ENABLE_DEMO_LOGIN !== "false";
  const [invStats, setInvStats] = useState<{
    total_items: number;
    low_stock_count: number;
    expiring_count: number;
  } | null>(null);
  const [billStats, setBillStats] = useState<{
    pending_count: number;
    total_bills: number;
  } | null>(null);

  const loadMetrics = useCallback(async () => {
    if (hasPermission("inventory.read")) {
      try {
        const res = await api.getInventory({ filter: "summary" });
        setInvStats(res.summary);
      } catch {
        setInvStats(null);
      }
    } else {
      setInvStats(null);
    }
    if (hasPermission("bills.read")) {
      try {
        const res = await api.getBills({ filter: "summary" });
        setBillStats(res.summary);
      } catch {
        setBillStats(null);
      }
    } else {
      setBillStats(null);
    }
  }, [hasPermission]);

  const handleRoleSwitch = async (email: string) => {
    if (switchingEmail || user?.email === email) return;
    setSwitchingEmail(email);
    try {
      await login(email, "HospitalDemo!2026");
    } finally {
      setSwitchingEmail(null);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  const grantedCount = permissions
    ? Object.values(permissions.permissions).filter((p) => p.allowed).length
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b-2 border-[#0A0A0A] pb-4">
        <div>
          <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#E10600]">
            01 // Command Center &amp; Overview
          </div>
          <h1 className="mt-1 text-2xl font-extrabold uppercase tracking-tight text-[#0A0A0A]">
            Hospital Operations Overview
          </h1>
          <p className="mt-0.5 font-mono text-xs text-neutral-600">
            {user?.hospital_name} — {user?.full_name} ({user?.roles.join(", ")})
          </p>
        </div>
        <div className="border border-[#0A0A0A] bg-white px-4 py-2 text-right">
          <div className="font-mono text-[9px] uppercase tracking-[0.14em] text-neutral-500">
            Granted Matrix Keys
          </div>
          <div className="font-mono text-lg font-bold tabular-nums text-[#0A0A0A]">
            {String(grantedCount).padStart(2, "0")} ACTIVE
          </div>
        </div>
      </div>

      {demoLoginEnabled && (
        <div className="border border-[#0A0A0A] bg-white">
          <div className="border-b border-neutral-300 bg-[#F4F3EF] px-3.5 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-neutral-700">
            Demo Role Switcher // Instant Session Switch
          </div>
          <div className="flex flex-wrap divide-x divide-y divide-neutral-300">
            {DEMO_ROLES.map((acc) => {
              const isActive = user?.email === acc.email;
              return (
                <button
                  key={acc.email}
                  type="button"
                  disabled={switchingEmail !== null}
                  onClick={() => handleRoleSwitch(acc.email)}
                  className={`px-3.5 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.06em] transition ${
                    isActive
                      ? "bg-[#E10600] text-white"
                      : "bg-white text-[#0A0A0A] hover:bg-[#F4F3EF]"
                  }`}
                >
                  {switchingEmail === acc.email ? "Switching..." : acc.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-px border border-[#0A0A0A] bg-[#0A0A0A] sm:grid-cols-2 lg:grid-cols-4">
        <div className="bg-white p-5">
          <div className="flex items-center justify-between font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-500">
            <span>Inventory Items</span>
            <span>01</span>
          </div>
          <div className="mt-3 text-3xl font-extrabold tabular-nums tracking-tight text-[#0A0A0A]">
            {hasPermission("inventory.read") ? invStats?.total_items ?? "—" : "RESTRICTED"}
          </div>
        </div>

        <div className="bg-white p-5">
          <div className="flex items-center justify-between font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-500">
            <span>Low Stock Items</span>
            <span className="text-[#E10600]">02</span>
          </div>
          <div
            className={`mt-3 text-3xl font-extrabold tabular-nums tracking-tight ${
              hasPermission("inventory.read") ? "text-[#E10600]" : "text-neutral-400"
            }`}
          >
            {hasPermission("inventory.read") ? invStats?.low_stock_count ?? "—" : "RESTRICTED"}
          </div>
        </div>

        <div className="bg-white p-5">
          <div className="flex items-center justify-between font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-500">
            <span>Expiring (30 Days)</span>
            <span>03</span>
          </div>
          <div
            className={`mt-3 text-3xl font-extrabold tabular-nums tracking-tight ${
              hasPermission("inventory.read") ? "text-amber-700" : "text-neutral-400"
            }`}
          >
            {hasPermission("inventory.read") ? invStats?.expiring_count ?? "—" : "RESTRICTED"}
          </div>
        </div>

        <div className="bg-white p-5">
          <div className="flex items-center justify-between font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-500">
            <span>Pending Bills</span>
            <span>04</span>
          </div>
          <div className="mt-3 text-3xl font-extrabold tabular-nums tracking-tight text-[#0A0A0A]">
            {hasPermission("bills.read") ? billStats?.pending_count ?? "—" : "RESTRICTED"}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <ChatPanel onDataChanged={loadMetrics} />
        </div>

        <div className="border border-[#0A0A0A] bg-white lg:col-span-4">
          <div className="border-b border-[#0A0A0A] bg-[#F4F3EF] px-5 py-3.5">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#E10600]">
              Policy Matrix
            </div>
            <h2 className="mt-0.5 text-sm font-extrabold uppercase tracking-[0.06em] text-[#0A0A0A]">
              Effective Role Permissions
            </h2>
            <p className="mt-1 text-[11px] text-neutral-600">
              Authoritative permissions enforced by the backend engine.
            </p>
          </div>
          <div className="divide-y divide-neutral-200">
            {permissions &&
              Object.values(permissions.permissions).map((perm) => (
                <div
                  key={perm.permission_key}
                  className="flex items-center justify-between gap-2 px-5 py-3 text-xs"
                >
                  <div className="min-w-0">
                    <div className="font-mono text-xs font-semibold text-[#0A0A0A]">
                      {perm.permission_key}
                    </div>
                    {Object.keys(perm.constraints).length > 0 && (
                      <div className="mt-0.5 font-mono text-[10px] text-neutral-500">
                        {JSON.stringify(perm.constraints)}
                      </div>
                    )}
                  </div>
                  <Badge variant={perm.allowed ? "success" : "outline"}>
                    {perm.allowed ? "Allow" : "Deny"}
                  </Badge>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
