"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const path = usePathname();
  const active = href === "/" ? path === "/" || path.startsWith("/runs") : path.startsWith(href);
  return (
    <Link
      href={href}
      className={
        "rounded-lg px-3.5 py-1.5 text-sm transition-colors " +
        (active
          ? "bg-indigo-50 font-semibold text-indigo-600"
          : "font-medium text-slate-500 hover:bg-indigo-50 hover:text-indigo-600")
      }
    >
      {children}
    </Link>
  );
}
