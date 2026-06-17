import type { Metadata } from "next";
import "./globals.css";
import { NavLink } from "@/lib/nav";

export const metadata: Metadata = {
  title: "Order Supervisor",
  description: "Long-running AI supervisor for a single order",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <header className="border-b border-line">
          <div className="mx-auto flex max-w-[1120px] items-center justify-between px-8 py-5">
            <div className="text-xl font-bold tracking-tight">Order Supervisor</div>
            <nav className="flex gap-1.5">
              <NavLink href="/">Runs</NavLink>
              <NavLink href="/supervisors">Supervisors</NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-[1120px] px-8 py-7">{children}</main>
      </body>
    </html>
  );
}
