const CARDS = [
  { label: "Active runs", value: "—" },
  { label: "Pending approvals", value: "—" },
  { label: "Publish ready", value: "—" },
];

export default function DashboardPage() {
  return (
    <main className="flex min-h-screen flex-col gap-8 p-10">
      <header className="flex flex-col gap-1 border-b border-border pb-4">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">
          SWE Drip
        </p>
        <h1 className="font-sans text-3xl font-semibold">Dashboard</h1>
      </header>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {CARDS.map((card) => (
          <div key={card.label} className="border border-border bg-card p-6">
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              {card.label}
            </p>
            <p className="mt-2 font-mono text-2xl text-primary">{card.value}</p>
          </div>
        ))}
      </section>

      <p className="max-w-prose text-sm text-muted-foreground">
        Pipeline shell online. Feature screens land in later PBIs.
      </p>
    </main>
  );
}
