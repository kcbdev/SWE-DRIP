"use client";

import { useEffect, useState } from "react";

import { isAdmin } from "@/lib/api";
import { type BrandConstants, fetchBrand } from "@/lib/settings";

/** Brand-lock constants display (palette, typeface, forbidden elements). Read-only in v1. */
export function BrandConstantsView({ role }: { role?: string }) {
  const [brand, setBrand] = useState<BrandConstants | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchBrand()
      .then(setBrand)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  if (error) {
    return (
      <p className="border border-destructive p-4 font-mono text-xs text-destructive">
        Failed to load brand constants: {error}
      </p>
    );
  }

  if (!brand) {
    return <p className="font-mono text-xs text-muted-foreground">Loading brand constants...</p>;
  }

  return (
    <section className="border border-border bg-card p-4" data-testid="brand-constants">
      <h2 className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
        Brand-Lock Constants
      </h2>
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        Palette, typeface, and forbidden elements. Edits require Admin + confirmation.
      </p>

      <div className="mt-4 flex flex-col gap-4">
        {/* Palette */}
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Palette
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(brand.palette).map(([name, hex]) => (
              <div key={name} className="flex items-center gap-2 border border-border px-2 py-1">
                <div
                  className="h-4 w-4 border border-border"
                  style={{ backgroundColor: hex }}
                />
                <span className="font-mono text-xs text-foreground">
                  {name}: {hex}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Typeface */}
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Typeface
          </p>
          <p className="mt-1 font-mono text-sm text-foreground">{brand.typeface}</p>
        </div>

        {/* Forbidden elements */}
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Forbidden Elements
          </p>
          <ul className="mt-1 list-inside list-disc font-mono text-sm text-foreground">
            {brand.forbidden.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
