import { NavLink } from "react-router-dom";

import { cn } from "../../lib/utils";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/runs", label: "Runs" },
  { to: "/launch", label: "Launch Run" },
  { to: "/data", label: "Data Management" },
  { to: "/health", label: "System Health" },
];

export default function Sidebar() {
  return (
    <aside className="w-full border-b border-line bg-panel/85 px-4 py-4 md:w-64 md:border-b-0 md:border-r md:px-5">
      <div className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">PolicyOS Runtime</p>
        <h1 className="text-xl font-semibold">Navigator</h1>
      </div>
      <nav className="flex gap-2 md:flex-col">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              cn(
                "rounded-xl border px-3 py-2 text-sm font-medium transition",
                isActive
                  ? "border-text/20 bg-text/5 text-text"
                  : "border-transparent bg-transparent text-muted hover:border-line hover:bg-panel",
              )
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
