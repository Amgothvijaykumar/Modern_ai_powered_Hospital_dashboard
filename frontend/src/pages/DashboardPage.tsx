import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Clock, FileText, Package, ShieldCheck } from "lucide-react";
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
    <div className="space-y-4">
      {/* Top Bento Row: Hero Banner (8 cols) + Active Matrix Tile (4 cols) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-sm lg:col-span-8">
          <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-[11px] font-semibold text-indigo-700">
            01 // Command Center Bento
          </div>
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-slate-950 sm:text-3xl">
            Hospital Operations Overview
          </h1>
          <p className="mt-1 text-xs text-slate-500 sm:text-sm">
            Signed in at <strong className="text-slate-800">{user?.hospital_name}</strong> as{" "}
            <strong className="text-slate-800">{user?.full_name}</strong> ({user?.roles.join(", ")})
          </p>
        </div>

        <div className="flex flex-col justify-between rounded-3xl bg-slate-950 p-6 text-white shadow-sm lg:col-span-4">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase tracking-wider text-slate-400">
              Granted Permissions
            </span>
            <ShieldCheck className="h-5 w-5 text-indigo-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-4xl font-extrabold tabular-nums">
              {String(grantedCount).padStart(2, "0")}
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
              Active Rules
            </span>
          </div>
        </div>
      </div>

      {/* Demo Role Switcher Bento Strip */}
      {demoLoginEnabled && (
        <div className="rounded-3xl border border-slate-200/90 bg-white p-4 shadow-sm">
          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 px-1">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Demo Role Switcher · Instant Session Switch
            </span>
            <span className="text-[11px] text-slate-400">Test RBAC &amp; Approval Routing live</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {DEMO_ROLES.map((acc) => {
              const isActive = user?.email === acc.email;
              return (
                <button
                  key={acc.email}
                  type="button"
                  disabled={switchingEmail !== null}
                  onClick={() => handleRoleSwitch(acc.email)}
                  className={`rounded-xl px-3.5 py-2 text-xs font-semibold transition-all ${
                    isActive
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "border border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300 hover:bg-white"
                  }`}
                >
                  {switchingEmail === acc.email ? "Switching..." : acc.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 4-Tile Bento KPI Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-3xl border border-slate-200/90 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Inventory Items</span>
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
              <Package className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-extrabold tabular-nums tracking-tight text-slate-950">
            {hasPermission("inventory.read") ? invStats?.total_items ?? "—" : "Restricted"}
          </div>
          <div className="mt-1 font-mono text-[11px] text-slate-400">Active catalog SKUs</div>
        </div>

        <div className="rounded-3xl border border-rose-200/70 bg-rose-50/40 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-700">Low Stock Alert</span>
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-rose-100 text-rose-600">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </div>
          <div
            className={`mt-4 text-3xl font-extrabold tabular-nums tracking-tight ${
              hasPermission("inventory.read") ? "text-rose-600" : "text-slate-400"
            }`}
          >
            {hasPermission("inventory.read") ? invStats?.low_stock_count ?? "—" : "Restricted"}
          </div>
          <div className="mt-1 font-mono text-[11px] text-rose-500/80">Below safety threshold</div>
        </div>

        <div className="rounded-3xl border border-amber-200/70 bg-amber-50/40 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-800">Expiring (30 Days)</span>
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
              <Clock className="h-4 w-4" />
            </div>
          </div>
          <div
            className={`mt-4 text-3xl font-extrabold tabular-nums tracking-tight ${
              hasPermission("inventory.read") ? "text-amber-700" : "text-slate-400"
            }`}
          >
            {hasPermission("inventory.read") ? invStats?.expiring_count ?? "—" : "Restricted"}
          </div>
          <div className="mt-1 font-mono text-[11px] text-amber-700/80">Upcoming batch expiry</div>
        </div>

        <div className="rounded-3xl border border-emerald-200/70 bg-emerald-50/40 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-800">Pending Bills</span>
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <FileText className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-4 text-3xl font-extrabold tabular-nums tracking-tight text-slate-950">
            {hasPermission("bills.read") ? billStats?.pending_count ?? "—" : "Restricted"}
          </div>
          <div className="mt-1 font-mono text-[11px] text-emerald-700/80">Awaiting settlement</div>
        </div>
      </div>

      {/* Main Bento Workspace: Chat Console (8 cols) + Effective Permissions Matrix (4 cols) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <ChatPanel onDataChanged={loadMetrics} />
        </div>

        <div className="flex flex-col rounded-3xl border border-slate-200/90 bg-white shadow-sm lg:col-span-4">
          <div className="border-b border-slate-100 px-6 py-4">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-wider text-indigo-600">
              Policy Matrix
            </div>
            <h2 className="mt-1 text-base font-bold text-slate-950">
              Effective Role Permissions
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Authoritative rules enforced by the backend policy engine.
            </p>
          </div>
          <div className="divide-y divide-slate-100 p-2">
            {permissions &&
              Object.values(permissions.permissions).map((perm) => (
                <div
                  key={perm.permission_key}
                  className="flex items-center justify-between gap-2 rounded-2xl px-4 py-3 text-xs transition hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <div className="font-mono text-xs font-semibold text-slate-900">
                      {perm.permission_key}
                    </div>
                    {Object.keys(perm.constraints).length > 0 && (
                      <div className="mt-0.5 font-mono text-[10px] text-slate-500">
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
