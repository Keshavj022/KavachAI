import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  MessageSquareWarning,
  Phone,
  ShieldCheck,
  ShieldHalf,
  Users,
  FileWarning,
  LogOut,
} from "lucide-react";
import PhoneFrame from "../../components/PhoneFrame";
import Brand from "../../components/Brand";
import LanguageToggle from "../../components/LanguageToggle";
import { useAuth } from "../../store/auth";

const NAV = [
  { to: "/app", icon: Phone, labelKey: "nav.call", end: true },
  { to: "/app/decoy", icon: ShieldCheck, labelKey: "nav.decoy", end: false },
  { to: "/app/shield", icon: MessageSquareWarning, labelKey: "nav.shield", end: false },
  { to: "/app/report", icon: FileWarning, labelKey: "nav.report", end: false },
  { to: "/app/guide", icon: ShieldHalf, labelKey: "nav.staySafe", end: false },
  { to: "/app/contacts", icon: Users, labelKey: "nav.contacts", end: false },
];

export default function ConsumerLayout() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const logout = useAuth((s) => s.logout);

  return (
    <PhoneFrame>
      <div className="flex h-full flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between gap-2 border-b border-black/5 bg-consumer-surface px-3 pb-2 pt-8">
          <Brand size="sm" />
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <button
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
              className="flex items-center gap-1 text-xs font-medium text-consumer-muted hover:text-consumer-ink"
              aria-label={t("nav.signOut")}
            >
              <LogOut size={14} />
            </button>
          </div>
        </header>

        {/* Page */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>

        {/* Bottom nav */}
        <nav className="grid grid-cols-6 border-t border-black/5 bg-consumer-surface">
          {NAV.map(({ to, icon: Icon, labelKey, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 py-2.5 text-[10px] font-medium leading-tight transition ${
                  isActive
                    ? "text-consumer-accent"
                    : "text-consumer-muted hover:text-consumer-ink"
                }`
              }
            >
              <Icon size={19} strokeWidth={2} />
              <span className="px-0.5 text-center">{t(labelKey)}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </PhoneFrame>
  );
}
