import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./store/auth";
import type { Role } from "./api/types";

import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import ConsumerLayout from "./pages/consumer/ConsumerLayout";
import LiveCall from "./pages/consumer/LiveCall";
import DecoyCallView from "./pages/consumer/DecoyCallView";
import GuideView from "./pages/consumer/GuideView";
import ShieldChat from "./pages/consumer/ShieldChat";
import ReportForm from "./pages/consumer/ReportForm";
import Contacts from "./pages/consumer/Contacts";

// Authority views pull in the heavy data-viz libraries (force graph, leaflet,
// charts). Lazy-load them so the consumer (hero) bundle stays small.
const AuthorityLayout = lazy(() => import("./pages/authority/AuthorityLayout"));
const Dashboard = lazy(() => import("./pages/authority/Dashboard"));
const FraudGraph = lazy(() => import("./pages/authority/FraudGraph"));
const ReportsTable = lazy(() => import("./pages/authority/ReportsTable"));
const HotspotMap = lazy(() => import("./pages/authority/HotspotMap"));
const CaseDetail = lazy(() => import("./pages/authority/CaseDetail"));

/** Guards a subtree to authenticated users of a given role. */
function RequireRole({
  role,
  children,
}: {
  role: Role;
  children: React.ReactNode;
}) {
  const { user, role: userRole, initialized } = useAuth();
  if (!initialized) return <FullPageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  if (userRole !== role) {
    // Logged in as the other role — send to their home.
    return <Navigate to={userRole === "authority" ? "/authority" : "/app"} replace />;
  }
  return <>{children}</>;
}

function FullPageLoader() {
  return (
    <div className="flex h-full items-center justify-center bg-consumer-bg text-consumer-muted">
      <span className="animate-pulse font-sans text-sm">Loading…</span>
    </div>
  );
}

/** Sends an already-authenticated user away from the auth pages. */
function RedirectIfAuthed({ children }: { children: React.ReactNode }) {
  const { user, role, initialized } = useAuth();
  if (!initialized) return <FullPageLoader />;
  if (user) {
    return <Navigate to={role === "authority" ? "/authority" : "/app"} replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const loadSession = useAuth((s) => s.loadSession);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <Login />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthed>
            <Register />
          </RedirectIfAuthed>
        }
      />

      {/* Consumer (citizen) */}
      <Route
        path="/app"
        element={
          <RequireRole role="citizen">
            <ConsumerLayout />
          </RequireRole>
        }
      >
        <Route index element={<LiveCall />} />
        <Route path="decoy" element={<DecoyCallView />} />
        <Route path="guide" element={<GuideView />} />
        <Route path="shield" element={<ShieldChat />} />
        <Route path="report" element={<ReportForm />} />
        <Route path="contacts" element={<Contacts />} />
      </Route>

      {/* Authority */}
      <Route
        path="/authority"
        element={
          <RequireRole role="authority">
            <Suspense fallback={<FullPageLoader />}>
              <AuthorityLayout />
            </Suspense>
          </RequireRole>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="graph" element={<FraudGraph />} />
        <Route path="reports" element={<ReportsTable />} />
        <Route path="reports/:id" element={<CaseDetail />} />
        <Route path="map" element={<HotspotMap />} />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
