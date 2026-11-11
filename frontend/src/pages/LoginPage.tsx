import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Languages,
  Lock,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const DEMO_ACCOUNTS = [
  { code: "01", role: "Admin", label: "Hospital A Admin", email: "admin.a@metrogeneral.org", scope: "Metro General", accent: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  { code: "02", role: "Billing", label: "Billing Manager", email: "billing.a@metrogeneral.org", scope: "Metro General", accent: "bg-amber-50 text-amber-800 border-amber-200" },
  { code: "03", role: "Pharmacy", label: "Pharmacist — Priya", email: "pharmacist.a@metrogeneral.org", scope: "Metro General", accent: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { code: "04", role: "Pharmacy", label: "Pharmacist — Ravi", email: "ravi.a@metrogeneral.org", scope: "Metro General", accent: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { code: "05", role: "Desk", label: "Front Desk", email: "frontdesk.a@metrogeneral.org", scope: "Metro General", accent: "bg-sky-50 text-sky-700 border-sky-200" },
  { code: "06", role: "Doctor", label: "Attending Doctor", email: "doctor.a@metrogeneral.org", scope: "Metro General", accent: "bg-purple-50 text-purple-700 border-purple-200" },
  { code: "07", role: "Admin", label: "Hospital B Admin", email: "admin.b@citycare.org", scope: "City Care", accent: "bg-rose-50 text-rose-700 border-rose-200" },
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin.a@metrogeneral.org");
  const [password, setPassword] = useState("HospitalDemo!2026");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const showDemoAccounts = import.meta.env.VITE_ENABLE_DEMO_LOGIN !== "false";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Sign in failed. Verify your email and password.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F3F5F8] px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-4">
        {/* Top Bento Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200/90 bg-white px-5 py-3 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-white">
              <Activity className="h-4 w-4 text-indigo-400" />
            </div>
            <div>
              <div className="text-xs font-extrabold tracking-tight text-slate-950">
                MEDOPS AI
              </div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
                Multi-Tenant Hospital Control
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              RBAC + RLS Active
            </span>
            <span className="hidden rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-mono text-[11px] font-medium text-slate-600 sm:inline-flex">
              INR · Asia/Kolkata (IST)
            </span>
          </div>
        </div>

        {/* Main Bento Grid: Hero (7 cols) + Login Card (5 cols) */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* Hero Bento Card */}
          <div
            className={`flex flex-col justify-between rounded-3xl border border-slate-200/90 bg-white p-6 shadow-sm sm:p-10 ${
              showDemoAccounts ? "lg:col-span-7" : "lg:col-span-7"
            }`}
          >
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3.5 py-1.5 text-xs font-semibold text-indigo-700">
                <Sparkles className="h-3.5 w-3.5" />
                Permission-Aware Conversational Copilot
              </div>

              <h1 className="mt-5 text-4xl font-extrabold leading-[1.05] tracking-tight text-slate-950 sm:text-5xl lg:text-[52px]">
                Modern AI-Powered{" "}
                <span className="bg-gradient-to-r from-indigo-600 via-blue-600 to-cyan-600 bg-clip-text text-transparent">
                  Hospital Management
                </span>
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-600 sm:text-base">
                Control pharmacy inventory, GST/INR billing discounts, role access governance, and
                approval routing through natural language—enforced end-to-end by database
                row-level isolation, dry-run previews, and instant undo snapshots.
              </p>
            </div>

            {/* 3 Mini Feature Bento Tiles inside Hero */}
            <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-emerald-200/80 bg-emerald-50/70 p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-600 text-white">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <div className="mt-3 text-sm font-bold text-slate-900">Strict RBAC + RLS</div>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">
                  Tenant-isolated queries &amp; role overrides enforced on every tool call.
                </p>
              </div>

              <div className="rounded-2xl border border-indigo-200/80 bg-indigo-50/70 p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-600 text-white">
                  <RotateCcw className="h-4 w-4" />
                </div>
                <div className="mt-3 text-sm font-bold text-slate-900">Dry-Run &amp; Undo</div>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">
                  Preview affected rows &amp; financial deltas before committing, or undo cleanly.
                </p>
              </div>

              <div className="rounded-2xl border border-amber-200/80 bg-amber-50/70 p-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500 text-white">
                  <Languages className="h-4 w-4" />
                </div>
                <div className="mt-3 text-sm font-bold text-slate-900">Multilingual Input</div>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">
                  Understands English, Telugu &amp; Hinglish commands with identical guardrails.
                </p>
              </div>
            </div>
          </div>

          {/* Auth Sign-In Bento Card */}
          <div className="flex flex-col justify-between rounded-3xl border border-slate-200/90 bg-white p-6 shadow-sm sm:p-8 lg:col-span-5">
            <div>
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-indigo-600">
                  Workspace Access
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 font-mono text-[10px] font-medium text-slate-600">
                  JWT Session
                </span>
              </div>
              <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">
                Sign in to Hospital Portal
              </h2>
              <p className="mt-1.5 text-xs text-slate-500">
                Authenticate with your hospital credentials or pick a demo staff role below.
              </p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                    Hospital Staff Email
                  </label>
                  <Input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="staff@metrogeneral.org"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-slate-700">
                    Password
                  </label>
                  <Input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>

                {error && (
                  <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs font-medium text-rose-700">
                    {error}
                  </div>
                )}

                <Button type="submit" size="lg" className="w-full justify-between" disabled={submitting}>
                  <span className="flex items-center gap-2">
                    <Lock className="h-4 w-4" />
                    {submitting ? "Authenticating Session..." : "Sign In to Workspace"}
                  </span>
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </form>
            </div>

            <div className="mt-6 rounded-2xl border border-slate-100 bg-slate-50 p-4 text-xs text-slate-600">
              <div className="flex items-center justify-between font-semibold text-slate-800">
                <span>Demo Credentials Ready</span>
                <code className="rounded-lg bg-white px-2 py-0.5 text-[11px] font-semibold text-indigo-600 ring-1 ring-slate-200">
                  HospitalDemo!2026
                </code>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                All write operations pause for confirmation and log an immutable audit record.
              </p>
            </div>
          </div>
        </div>

        {/* Bottom Bento Row: Demo Profiles (8 cols) + Dark Guardrail Telemetry Tile (4 cols) */}
        {showDemoAccounts && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-sm lg:col-span-8">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-wider text-indigo-600">
                    Instant Role Preview
                  </span>
                  <h3 className="mt-0.5 text-base font-bold text-slate-950">
                    Select a Demo Staff Profile
                  </h3>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                  Click a tile to fill login form
                </span>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
                {DEMO_ACCOUNTS.map((acc) => {
                  const selected = email === acc.email;
                  return (
                    <button
                      key={acc.email}
                      type="button"
                      onClick={() => {
                        setEmail(acc.email);
                        setPassword("HospitalDemo!2026");
                      }}
                      className={`group flex flex-col justify-between rounded-2xl border p-3.5 text-left transition-all ${
                        selected
                          ? "border-slate-950 bg-slate-950 text-white shadow-md"
                          : "border-slate-200 bg-slate-50/70 text-slate-900 hover:border-slate-300 hover:bg-white"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                            selected
                              ? "border-indigo-400/40 bg-indigo-500/20 text-indigo-200"
                              : acc.accent
                          }`}
                        >
                          {acc.role}
                        </span>
                        <span
                          className={`font-mono text-[10px] ${
                            selected ? "text-slate-300" : "text-slate-400"
                          }`}
                        >
                          {acc.scope}
                        </span>
                      </div>
                      <div className="mt-2.5 text-xs font-bold">{acc.label}</div>
                      <div
                        className={`mt-0.5 truncate font-mono text-[10px] ${
                          selected ? "text-slate-300" : "text-slate-500"
                        }`}
                      >
                        {acc.email}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-col justify-between rounded-3xl bg-slate-950 p-6 text-white shadow-sm lg:col-span-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-[11px] font-semibold text-indigo-300">
                  Enterprise Guardrails
                </div>
                <h3 className="mt-4 text-xl font-bold leading-snug tracking-tight">
                  Built for High-Stakes Clinical &amp; Billing Operations
                </h3>
                <ul className="mt-4 space-y-2.5 text-xs text-slate-300">
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    <span>Approval routing for billing discounts exceeding manager caps</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    <span>Exact row-count verification required on writes &gt; 50 rows</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    <span>Prompt-injection resistant structured intent classification</span>
                  </li>
                </ul>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-2.5">
                <div className="rounded-2xl bg-white/10 p-3">
                  <div className="font-mono text-[10px] uppercase text-slate-400">Hospitals</div>
                  <div className="mt-1 text-lg font-extrabold">2 Tenants</div>
                </div>
                <div className="rounded-2xl bg-white/10 p-3">
                  <div className="font-mono text-[10px] uppercase text-slate-400">Audit Trail</div>
                  <div className="mt-1 text-lg font-extrabold">100% Logged</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
