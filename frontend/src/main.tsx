import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import { AuthProvider, useAuth } from "./lib/auth";
import { Loading, ToastProvider } from "./components/ui";
import Shell from "./components/Shell";
import { Invite, Login, Signup } from "./pages/Auth";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Chat from "./pages/Chat";
import Understand from "./pages/Understand";
import BlueprintPage from "./pages/Blueprint";
import StudioPage from "./pages/Studio";
import Approvals from "./pages/Approvals";
import Audit from "./pages/Audit";
import Activity from "./pages/Activity";
import HistoryPage from "./pages/History";
import Users from "./pages/settings/Users";
import Roles from "./pages/settings/Roles";
import Org from "./pages/settings/Org";
import ApiWidget from "./pages/settings/ApiWidget";
import Usage from "./pages/settings/Usage";

function Private({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  if (!me) return <Navigate to="/login" replace />;
  return <Shell>{children}</Shell>;
}

/** The website for visitors; Home for people who are signed in. */
function Root() {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  return me ? <Shell><Home /></Shell> : <Landing />;
}

function Public({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  return me ? <Navigate to="/" replace /> : <>{children}</>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Public><Login /></Public>} />
            <Route path="/signup" element={<Public><Signup /></Public>} />
            <Route path="/invite/:token" element={<Invite />} />
            <Route path="/" element={<Root />} />
            <Route path="/chat" element={<Private><Chat /></Private>} />
            <Route path="/chat/:cid" element={<Private><Chat /></Private>} />
            <Route path="/understand" element={<Private><Understand /></Private>} />
            <Route path="/studio" element={<Private><StudioPage /></Private>} />
            <Route path="/studio/:bid" element={<Private><StudioPage /></Private>} />
            <Route path="/blueprint" element={<Private><BlueprintPage /></Private>} />
            <Route path="/blueprint/:bid" element={<Private><BlueprintPage /></Private>} />
            <Route path="/approvals" element={<Private><Approvals /></Private>} />
            <Route path="/approvals/:did" element={<Private><Approvals /></Private>} />
            <Route path="/audit" element={<Private><Audit /></Private>} />
            <Route path="/activity" element={<Private><Activity /></Private>} />
            <Route path="/history" element={<Private><HistoryPage /></Private>} />
            <Route path="/history/:cid" element={<Private><HistoryPage /></Private>} />
            <Route path="/settings/users" element={<Private><Users /></Private>} />
            <Route path="/settings/roles" element={<Private><Roles /></Private>} />
            <Route path="/settings/org" element={<Private><Org /></Private>} />
            <Route path="/settings/api" element={<Private><ApiWidget /></Private>} />
            <Route path="/settings/usage" element={<Private><Usage /></Private>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  </StrictMode>,
);
