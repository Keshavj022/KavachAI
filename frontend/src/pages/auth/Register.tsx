import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Role } from "../../api/types";
import { useAuth } from "../../store/auth";
import { ApiError } from "../../api/client";
import { AuthShell, Field } from "./Login";

export default function Register() {
  const navigate = useNavigate();
  const register = useAuth((s) => s.register);
  const loading = useAuth((s) => s.loading);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("citizen");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const r = await register(email, password, fullName, role);
      navigate(r === "authority" ? "/authority" : "/app", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to create account. Try again.",
      );
    }
  }

  return (
    <AuthShell>
      <h1 className="font-display text-2xl font-bold text-consumer-ink">
        Create account
      </h1>
      <p className="mt-1 text-sm text-consumer-muted">
        A guardian for you and the people you protect.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <Field label="Full name" type="text" value={fullName} onChange={setFullName} />
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
          autoComplete="new-password"
        />

        <fieldset>
          <legend className="mb-1 text-sm font-medium text-consumer-ink">
            Account type
          </legend>
          <div className="flex gap-2">
            {(["citizen", "authority"] as Role[]).map((r) => (
              <button
                type="button"
                key={r}
                onClick={() => setRole(r)}
                className={`flex-1 rounded-xl border px-3 py-2.5 text-sm font-medium capitalize transition ${
                  role === r
                    ? "border-consumer-accent bg-consumer-accent/5 text-consumer-accent"
                    : "border-gray-200 text-consumer-muted hover:border-consumer-accent/40"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </fieldset>

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
          className="w-full rounded-xl bg-consumer-accent px-4 py-3 font-semibold text-white transition hover:bg-consumer-accent-dark disabled:opacity-60"
        >
          {loading ? "Creating…" : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-consumer-muted">
        Already registered?{" "}
        <Link to="/login" className="font-semibold text-consumer-accent hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
