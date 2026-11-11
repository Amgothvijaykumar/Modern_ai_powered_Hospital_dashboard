import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Lock } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const DEMO_ACCOUNTS = [
  { code: "01", label: "Admin (Hospital A)", email: "admin.a@metrogeneral.org", scope: "Metro General" },
  { code: "02", label: "Billing Manager (Hospital A)", email: "billing.a@metrogeneral.org", scope: "Metro General" },
  { code: "03", label: "Pharmacist — Priya", email: "pharmacist.a@metrogeneral.org", scope: "Metro General" },
  { code: "04", label: "Pharmacist — Ravi", email: "ravi.a@metrogeneral.org", scope: "Metro General" },
  { code: "05", label: "Front Desk (Hospital A)", email: "frontdesk.a@metrogeneral.org", scope: "Metro General" },
  { code: "06", label: "Doctor (Hospital A)", email: "doctor.a@metrogeneral.org", scope: "Metro General" },
  { code: "07", label: "Admin (Hospital B)", email: "admin.b@citycare.org", scope: "City Care" },
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
    <div className="min-h-screen bg-[#F4F3EF] p-4 sm:p-8 md:flex md:items-center md:justify-center">
      <div className="w-full max-w-5xl border border-[#0A0A0A] bg-white">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#0A0A0A] bg-[#0A0A0A] px-6 py-3 text-white">
          <div className="flex items-center gap-3">
            <span className="relative inline-flex h-5 w-5 items-center justify-center bg-[#E10600]">
              <span className="absolute h-3 w-1 bg-white" />
              <span className="absolute h-1 w-3 bg-white" />
            </span>
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
              SYS // 00 — HOSPITAL OPERATIONS AI AGENT
            </span>
          </div>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-neutral-400">
            MULTI-TENANT // RBAC // DRY-RUN SAFE
          </span>
        </div>

        <div className={`grid ${showDemoAccounts ? "md:grid-cols-12" : "md:grid-cols-1"}`}>
          <div
            className={`p-6 sm:p-10 ${
              showDemoAccounts ? "border-b border-[#0A0A0A] md:col-span-7 md:border-b-0 md:border-r" : ""
            }`}
          >
            <div className="border-t-4 border-[#E10600] pt-5">
              <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-500">
                Authentication Gateway
              </div>
              <h1 className="mt-2 text-3xl font-extrabold uppercase leading-[1.05] tracking-tight text-[#0A0A0A] sm:text-4xl">
                Hospital Operations Control
              </h1>
              <p className="mt-3 max-w-md text-xs leading-relaxed text-neutral-600">
                Permission-enforced conversational workspace for inventory management, GST/INR billing
                discounts, user access governance, and immutable operational auditing.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="mt-8 space-y-5">
              <div>
                <label className="mb-1.5 block font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-neutral-700">
                  01 / Hospital Staff Email
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
                <label className="mb-1.5 block font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-neutral-700">
                  02 / Access Password
                </label>
                <Input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {error && (
                <div className="border border-[#E10600] border-l-4 bg-[#FFF2F2] px-3 py-2.5 text-xs font-medium text-[#E10600]">
                  {error}
                </div>
              )}

              <Button type="submit" size="lg" className="w-full justify-between" disabled={submitting}>
                <span className="flex items-center gap-2">
                  <Lock className="h-3.5 w-3.5" />
                  {submitting ? "Authenticating Session..." : "Sign In to Workspace"}
                </span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </form>
          </div>

          {showDemoAccounts && (
            <div className="bg-[#F4F3EF]/60 p-6 sm:p-8 md:col-span-5">
              <div className="border-b border-[#0A0A0A] pb-3">
                <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#E10600]">
                  Directory Index
                </div>
                <h2 className="mt-1 text-sm font-extrabold uppercase tracking-[0.06em] text-[#0A0A0A]">
                  Demo Staff Profiles
                </h2>
                <p className="mt-1 text-[11px] text-neutral-600">
                  Select an operator below (password:{" "}
                  <code className="bg-white px-1 py-0.5 text-[10px] font-semibold">
                    HospitalDemo!2026
                  </code>
                  ).
                </p>
              </div>

              <div className="mt-4 divide-y divide-neutral-300 border border-[#0A0A0A] bg-white">
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
                      className={`flex w-full items-center justify-between border-l-4 px-3 py-2.5 text-left transition ${
                        selected
                          ? "border-l-[#E10600] bg-[#0A0A0A] text-white"
                          : "border-l-transparent bg-white text-[#0A0A0A] hover:bg-[#F4F3EF]"
                      }`}
                    >
                      <div className="min-w-0 pr-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`font-mono text-[10px] ${
                              selected ? "text-[#E10600]" : "text-neutral-400"
                            }`}
                          >
                            {acc.code}
                          </span>
                          <span className="truncate text-xs font-bold">{acc.label}</span>
                        </div>
                        <div
                          className={`mt-0.5 truncate pl-5 font-mono text-[10px] ${
                            selected ? "text-neutral-300" : "text-neutral-500"
                          }`}
                        >
                          {acc.email}
                        </div>
                      </div>
                      <span
                        className={`shrink-0 font-mono text-[9px] uppercase tracking-[0.1em] ${
                          selected ? "text-neutral-300" : "text-neutral-400"
                        }`}
                      >
                        {acc.scope}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
