import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Share2,
  Table2,
  Map as MapIcon,
  LogOut,
} from "lucide-react";
import Brand from "../../components/Brand";
import { useAuth } from "../../store/auth";

const NAV = [
  { to: "/authority", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/authority/graph", icon: Share2, label: "Fraud Graph", end: false },
  { to: "/authority/reports", icon: Table2, label: "Reports", end: false },
  { to: "/authority/map", icon: MapIcon, label: "Hotspot Map", end: false },
];

export default function AuthorityLayout() {
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);

  return (
    <div className="flex h-full min-h-screen bg-authority-base text-authority-text">
      {/* Left nav */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-authority-border bg-authority-surface">
        <div className="border-b border-authority-border px-5 py-4">
          <Brand tone="authority" />
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-authority-muted">
            Command Center
          </p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {NAV.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? "bg-authority-cyan/10 text-authority-cyan"
                    : "text-authority-muted hover:bg-white/5 hover:text-authority-text"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-authority-border p-3">
          <button
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-authority-muted transition hover:bg-white/5 hover:text-authority-red"
          >
            <LogOut size={18} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-authority-border bg-authority-surface px-6 py-3">
          <StatusBar />
          <div className="text-right">
            <p className="text-sm font-medium">{user?.full_name}</p>
            <p className="font-mono text-[11px] text-authority-muted">
              {user?.email}
            </p>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function StatusBar() {
  return (
    <div className="flex items-center gap-2">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-verdict-safe opacity-70" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-verdict-safe" />
      </span>
      <span className="font-mono text-xs uppercase tracking-wider text-authority-muted">
        Live feed active
      </span>
    </div>
  );
}
