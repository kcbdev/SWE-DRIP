"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { authClient } from "@/lib/auth-client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { error: signInError } = await authClient.signIn.email({ email, password });
    setBusy(false);
    if (signInError) {
      setError(signInError.message ?? "Sign-in failed");
      return;
    }
    router.push("/");
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-10">
      <form onSubmit={onSubmit} className="w-full max-w-sm border border-border bg-card p-8">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">SWE Drip</p>
        <h1 className="mt-1 font-sans text-2xl font-semibold">Sign in</h1>

        <label className="mt-6 block font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1 w-full border border-border bg-background px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-primary"
          />
        </label>

        <label className="mt-4 block font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full border border-border bg-background px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-primary"
          />
        </label>

        {error ? <p className="mt-4 font-mono text-xs text-destructive">{error}</p> : null}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full bg-primary px-4 py-2 font-mono text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="mt-3 font-mono text-xs text-muted-foreground">
          Invite-only. Ask an admin for access.
        </p>
      </form>
    </main>
  );
}
