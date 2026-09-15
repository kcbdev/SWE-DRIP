"use client";

import { useEffect, useState } from "react";

import { authClient } from "@/lib/auth-client";
import { AppShell } from "@/components/app-shell";
import { apiFetch, isAdmin, type ApiUser, type Role } from "@/lib/api";

const ROLES: Role[] = ["admin", "operator", "viewer"];

export default function UsersPage() {
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const [users, setUsers] = useState<ApiUser[]>([]);
  const [email, setEmail] = useState("");
  const [newRole, setNewRole] = useState<Role>("viewer");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setUsers(await apiFetch<ApiUser[]>("/api/users"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load users");
    }
  }

  useEffect(() => {
    if (isAdmin(role)) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  if (!isAdmin(role)) {
    return (
      <AppShell>
        <p className="font-mono text-sm text-muted-foreground">
          Admin role required. This screen is hidden for non-admins and the API returns 403.
        </p>
      </AppShell>
    );
  }

  async function invite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await apiFetch("/api/users", {
      method: "POST",
      body: JSON.stringify({ email, name: email.split("@")[0], role: newRole }),
    });
    setEmail("");
    await refresh();
  }

  async function changeRole(userId: string, nextRole: Role) {
    await apiFetch(`/api/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role: nextRole }),
    });
    await refresh();
  }

  async function deactivate(userId: string) {
    await apiFetch(`/api/users/${userId}/deactivate`, { method: "POST" });
    await refresh();
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <h1 className="font-sans text-2xl font-semibold">Users &amp; Roles</h1>

        <form onSubmit={invite} className="flex flex-wrap items-end gap-3 border border-border bg-card p-4">
          <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 block border border-border bg-background px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-primary"
            />
          </label>
          <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Role
            <select
              value={newRole}
              onChange={(event) => setNewRole(event.target.value as Role)}
              className="mt-1 block border border-border bg-background px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-primary"
            >
              {ROLES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            className="bg-primary px-4 py-2 font-mono text-sm text-primary-foreground hover:bg-primary/90"
          >
            Invite
          </button>
        </form>

        {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}

        <table className="w-full border border-border text-left font-mono text-sm">
          <thead className="bg-secondary text-xs uppercase tracking-widest text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t border-border">
                <td className="px-3 py-2">{user.email}</td>
                <td className="px-3 py-2">
                  <select
                    value={user.role}
                    onChange={(event) => void changeRole(user.id, event.target.value as Role)}
                    className="border border-border bg-background px-2 py-1"
                  >
                    {ROLES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {user.active ? "active" : "deactivated"}
                </td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    disabled={!user.active}
                    onClick={() => void deactivate(user.id)}
                    className="text-xs text-destructive disabled:opacity-40"
                  >
                    Deactivate
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
