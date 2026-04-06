"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Zap, Fingerprint, Key, ArrowRight, Eye, EyeOff, AlertCircle } from "lucide-react";
import { loginUser, registerUser } from "@/lib/api";

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/dashboard";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Username and password are required");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const res =
        mode === "login"
          ? await loginUser(username, password)
          : await registerUser(username, password);

      localStorage.setItem("token", res.access_token);
      // Also set cookie for server-side middleware auth check
      const isSecure = window.location.protocol === "https:";
      document.cookie = `token=${res.access_token}; path=/; max-age=${60 * 60 * 24}; SameSite=Lax${isSecure ? "; Secure" : ""}`;
      router.push(redirectTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[#0D0D0D]">
      <main className="w-full max-w-md">
        {/* Logo + Subtitle */}
        <div className="flex flex-col items-center mb-10">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="text-[#00F0FF] w-10 h-10 fill-current" />
            <h1 className="font-mono font-black text-xl tracking-tighter text-[#00F0FF]">
              CQ ENGINE
            </h1>
          </div>
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#B9CACB] opacity-50">
            Institutional Liquidity Gateway
          </p>
        </div>

        {/* Card */}
        <div className="glass-bg border border-white/5 rounded-sm p-8 relative">
          {/* Tab Toggle */}
          <div className="flex border-b border-[#3B494B]/20 mb-8">
            <button
              onClick={() => { setMode("login"); setError(null); }}
              className={`flex-1 py-3 text-sm font-mono tracking-wider transition-all ${
                mode === "login"
                  ? "border-b-2 border-[#00F0FF] text-[#00F0FF]"
                  : "text-[#B9CACB] opacity-50 hover:text-[#E5E2E1]"
              }`}
            >
              LOGIN
            </button>
            <button
              onClick={() => { setMode("register"); setError(null); }}
              className={`flex-1 py-3 text-sm font-mono tracking-wider transition-all ${
                mode === "register"
                  ? "border-b-2 border-[#00F0FF] text-[#00F0FF]"
                  : "text-[#B9CACB] opacity-50 hover:text-[#E5E2E1]"
              }`}
            >
              REGISTER
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-sm mb-6 text-sm bg-[#93000A]/20 border border-[#93000A]/30 text-[#FFB4AB]">
              <AlertCircle size={16} className="shrink-0" />
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block font-mono text-[10px] text-[#B9CACB] uppercase mb-2 tracking-widest">
                Trader ID
              </label>
              <div className="flex items-center bg-[#2A2A2A] px-4 py-3 rounded-sm input-focus-effect border-b border-transparent transition-all">
                <Fingerprint className="text-[#B9CACB] w-4 h-4 mr-3 shrink-0" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  autoComplete="username"
                  className="bg-transparent border-none focus:ring-0 text-[#E5E2E1] font-mono text-sm w-full placeholder:text-[#B9CACB]/30 outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block font-mono text-[10px] text-[#B9CACB] uppercase mb-2 tracking-widest">
                Access Key
              </label>
              <div className="flex items-center bg-[#2A2A2A] px-4 py-3 rounded-sm input-focus-effect border-b border-transparent transition-all">
                <Key className="text-[#B9CACB] w-4 h-4 mr-3 shrink-0" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  className="bg-transparent border-none focus:ring-0 text-[#E5E2E1] font-mono text-sm w-full placeholder:text-[#B9CACB]/30 outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-[#B9CACB]/50 hover:text-[#B9CACB] transition-colors ml-2 shrink-0"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#00F0FF] text-[#002022] font-mono font-bold text-sm py-4 rounded-sm hover:opacity-90 active:scale-[0.98] transition-all flex items-center justify-center gap-2 group mt-4 disabled:opacity-40 disabled:cursor-wait"
            >
              {loading
                ? "INITIALIZING..."
                : mode === "login"
                  ? "INITIALIZE SESSION"
                  : "CREATE ACCOUNT"}
              {!loading && <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />}
            </button>
          </form>

          {/* Status Footer */}
          <div className="mt-8 flex items-center justify-center gap-4 border-t border-[#3B494B]/10 pt-6">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-[#02C953] animate-pulse" />
              <span className="font-mono text-[9px] text-[#B9CACB] uppercase tracking-tighter">
                Engine Status: Online
              </span>
            </div>
            <div className="w-1 h-1 rounded-full bg-[#3B494B]/30" />
            <span className="font-mono text-[9px] text-[#B9CACB] uppercase tracking-tighter">
              {mode === "login"
                ? "No account? Switch to Register"
                : "Have an account? Switch to Login"}
            </span>
          </div>
        </div>

        {/* Disclaimer Footer */}
        <footer className="mt-8 text-center">
          <p className="font-mono text-[9px] text-[#B9CACB] opacity-40 uppercase tracking-widest leading-relaxed">
            By entering the engine, you acknowledge that algorithmic trading involves risk.<br />
            CryptoQuant Engine v2.0
          </p>
        </footer>
      </main>
    </div>
  );
}
