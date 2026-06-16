import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Order Supervisor",
  description: "Long-running AI supervisor for a single order",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-6xl px-6 py-6">
          <header className="mb-6 flex items-center justify-between border-b border-slate-200 pb-4">
            <h1 className="text-xl font-semibold">Order Supervisor</h1>
            <nav className="flex gap-4 text-sm text-slate-600">
              <a href="/" className="hover:text-slate-900">Runs</a>
              <a href="/supervisors" className="hover:text-slate-900">Supervisors</a>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
