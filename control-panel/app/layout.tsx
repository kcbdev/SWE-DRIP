import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SWE Drip — Control Panel",
  description: "Autonomous POD design pipeline control panel",
  // `app/icon.svg` is picked up automatically; declaring it too keeps the tag
  // explicit so browsers stop falling back to /favicon.ico (which 404'd).
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
