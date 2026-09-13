import {
  formatUsd,
  relativeTime,
  spendPercent,
  type DashboardSummary,
} from "@/lib/dashboard";

export interface DashboardViewProps {
  summary: DashboardSummary | null;
  error?: string | null;
}

function StatCard({
  label,
  children,
  footer,
}: {
  label: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="border border-border bg-card p-6">
      <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">{label}</p>
      <div className="mt-2 font-mono text-2xl text-primary">{children}</div>
      {footer ? <div className="mt-2 font-mono text-xs text-muted-foreground">{footer}</div> : null}
    </div>
  );
}

export function DashboardView({ summary, error }: DashboardViewProps) {
  if (!summary) {
    return (
      <p className="font-mono text-sm text-destructive">
        {error ?? "Loading dashboard…"}
      </p>
    );
  }

  const pendingCount = summary.pending_approvals.count;
  const spend = summary.spend;
  const collections = summary.collections;

  return (
    <div className="flex flex-col gap-6 lg:flex-row">
      <div className="flex flex-1 flex-col gap-6">
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Awaiting approval"
            footer={<a href="/approvals" className="text-primary">View approvals</a>}
          >
            {pendingCount === null ? "—" : pendingCount}
          </StatCard>

          <StatCard
            label="Monthly spend"
            footer={spend ? `cap ${formatUsd(spend.cap_usd)}` : "source unavailable"}
          >
            {spend ? (
              <span className={spend.warning ? "text-warning" : ""} data-warning={spend.warning}>
                {formatUsd(spend.spend_usd)} ({spendPercent(spend)}%)
              </span>
            ) : (
              "—"
            )}
          </StatCard>

          <StatCard
            label="Active collections"
            footer={
              collections?.at_risk ? (
                <span className="text-warning" data-at-risk="true">
                  at risk
                </span>
              ) : (
                "healthy"
              )
            }
          >
            {collections ? collections.count : "—"}
          </StatCard>
        </section>

        <section className="border border-border bg-card">
          <h2 className="border-b border-border px-4 py-2 font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Recent activity
          </h2>
          {summary.activity === null ? (
            <p className="px-4 py-3 font-mono text-sm text-muted-foreground">source unavailable</p>
          ) : summary.activity.length === 0 ? (
            <p className="px-4 py-3 font-mono text-sm text-muted-foreground">No recent activity.</p>
          ) : (
            <ul className="divide-y divide-border">
              {summary.activity.map((item, index) => (
                <li key={`${item.action}-${index}`} className="flex items-center justify-between px-4 py-2 font-mono text-xs">
                  <span className="text-primary">{item.action}</span>
                  <span className="text-muted-foreground">
                    {item.entity_type}
                    {item.entity_id ? `:${item.entity_id}` : ""} · {item.actor}
                  </span>
                  <span className="text-muted-foreground">{relativeTime(item.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <aside className="w-full border border-border bg-card lg:w-72">
        <h2 className="border-b border-border px-4 py-2 font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Pending approvals
        </h2>
        {pendingCount === null ? (
          <p className="px-4 py-3 font-mono text-sm text-muted-foreground">source unavailable</p>
        ) : summary.pending_approvals.items.length === 0 ? (
          <p className="px-4 py-3 font-mono text-sm text-muted-foreground">No pending approvals.</p>
        ) : (
          <ul className="divide-y divide-border">
            {summary.pending_approvals.items.map((item, index) => (
              <li key={item.id ?? index} className="px-4 py-2 font-mono text-xs text-foreground">
                {item.type ?? "approval"}
                {item.collection ? ` · ${item.collection}` : ""}
              </li>
            ))}
          </ul>
        )}
        <div className="border-t border-border px-4 py-2">
          <a href="/approvals" className="font-mono text-xs text-primary">
            View all
          </a>
        </div>
      </aside>
    </div>
  );
}
