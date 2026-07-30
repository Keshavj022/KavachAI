import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import Brand from "../../components/Brand";
import { useAuth } from "../../store/auth";
import { ApiError } from "../../api/client";

export default function Login() {
  const navigate = useNavigate();
  const login = useAuth((s) => s.login);
  const loading = useAuth((s) => s.loading);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const role = await login(email, password);
      navigate(role === "authority" ? "/authority" : "/app", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to sign in. Try again.",
      );
    }
  }

  function fill(kind: "citizen" | "authority") {
    setEmail(
      kind === "authority" ? "authority@kavach.demo" : "citizen@kavach.demo",
    );
    setPassword("password123");
  }

  return (
    <AuthShell>
      <h1 className="font-display text-2xl font-bold text-consumer-ink">
        Sign in
      </h1>
      <p className="mt-1 text-sm text-consumer-muted">
        Protection that watches on your behalf.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="username"
        />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />

        {error && (
          <p
            role="alert"
            className="rounded-lg bg-verdict-danger/10 px-3 py-2 text-sm text-verdict-danger"
          >
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-consumer-accent px-4 py-3 font-semibold text-white transition hover:bg-consumer-accent-dark disabled:opacity-60"
        >
          {loading ? "Signing in…" : "Sign in"}
          {!loading && <ArrowRight size={18} />}
        </button>
      </form>

      <div className="mt-5 rounded-xl border border-consumer-bg bg-consumer-bg/60 p-3">
        <p className="text-xs font-medium text-consumer-muted">Demo accounts</p>
        <div className="mt-2 flex gap-2">
          <button
            onClick={() => fill("citizen")}
            className="flex-1 rounded-lg border border-consumer-accent/30 px-3 py-2 text-xs font-medium text-consumer-accent hover:bg-consumer-accent/5"
          >
            Citizen
          </button>
          <button
            onClick={() => fill("authority")}
            className="flex-1 rounded-lg border border-consumer-accent/30 px-3 py-2 text-xs font-medium text-consumer-accent hover:bg-consumer-accent/5"
          >
            Authority
          </button>
        </div>
      </div>

      <p className="mt-6 text-center text-sm text-consumer-muted">
        No account?{" "}
        <Link
          to="/register"
          className="font-semibold text-consumer-accent hover:underline"
        >
          Create one
        </Link>
      </p>
    </AuthShell>
  );
}

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full items-center justify-center bg-consumer-bg px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex justify-center">
          <Brand size="lg" />
        </div>
        <div className="rounded-2xl bg-consumer-surface p-6 shadow-card">
          {children}
        </div>
        <p className="mt-4 text-center text-xs text-consumer-muted">
          Real police never arrest you over a video call.
        </p>
      </div>
    </div>
  );
}

export function Field({
  label,
  type,
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-consumer-ink">
        {label}
      </span>
      <input
        type={type}
        value={value}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        required
        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-consumer-ink outline-none transition focus:border-consumer-accent"
      />
    </label>
  );
}
