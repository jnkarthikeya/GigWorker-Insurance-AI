import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

import Sidebar from "./components/layout/Sidebar";
import Header from "./components/layout/Header";
import AdminPage from "./pages/AdminPage";
import ClaimPage from "./pages/ClaimPage";
import Dashboard from "./pages/Dashboard";
import LoginPage from "./pages/LoginPage";
import { useWebSocket } from "./hooks/useWebSocket";

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

function AnimatedRoutes({ wsMessage, userRole }) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div key={location.pathname} variants={pageVariants} initial="initial" animate="animate" exit="exit">
        <Routes location={location}>
          <Route path="/" element={<Dashboard wsMessage={wsMessage} />} />
          <Route path="/claim" element={<ClaimPage wsMessage={wsMessage} />} />
          <Route path="/admin" element={userRole === "admin" ? <AdminPage /> : <Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  const [session, setSession] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const user = localStorage.getItem("user");

    if (!token || !user) {
      setSession(null);
      return;
    }

    try {
      setSession({
        token,
        user: JSON.parse(user),
      });
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user");
      setSession(null);
    }
  }, []);

const wsUrl = useMemo(() => {
  const userId = session?.user?.user_id;
  if (!userId) return null;

  const baseUrl = import.meta.env.VITE_API_URL;

  const wsBase = baseUrl
    .replace("https://", "wss://")
    .replace("http://", "ws://");

  return `${wsBase}/ws/${userId}`;
}, [session]);

  const { status, lastMessage } = useWebSocket(wsUrl, { debug: false, enableMockFallback: false });

  const handleAuth = (authPayload) => {
    const user = {
      user_id: authPayload.user_id,
      name: authPayload.name,
      role: authPayload.role || "user",
    };

    localStorage.setItem("access_token", authPayload.access_token);
    localStorage.setItem("refresh_token", authPayload.refresh_token);
    localStorage.setItem("user", JSON.stringify(user));
    setSession({ token: authPayload.access_token, user });
  };

  if (!session) {
    return <LoginPage onAuthenticated={handleAuth} />;
  }

  return (
    <BrowserRouter>
      <div className="min-h-screen grid-bg bg-[#040d1a] text-slate-100">
        <div
          className="fixed inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at top, rgba(34,211,238,0.16), transparent 34%), radial-gradient(circle at bottom right, rgba(16,185,129,0.1), transparent 28%)",
          }}
        />

        <Sidebar />
        <Header wsStatus={status} />

        <main className="relative z-10 min-h-screen px-4 pb-28 pt-20 md:ml-[220px] md:px-6 md:pb-8">
          <div className="mx-auto max-w-7xl">
            <AnimatedRoutes wsMessage={lastMessage} userRole={session.user.role} />
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}
