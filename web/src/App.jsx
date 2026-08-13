/** Marshrutlar va umumiy karkas. */

import { Navigate, Route, Routes } from "react-router-dom";

import Aurora from "./components/Aurora";
import Toasts from "./components/Toasts";
import { useAuth } from "./context/AuthContext";
import Admin from "./pages/Admin";
import Chat from "./pages/Chat";
import Download from "./pages/Download";
import Gallery from "./pages/Gallery";
import Login from "./pages/Login";
import Models from "./pages/Models";
import Signup from "./pages/Signup";

/** Faqat kirgan foydalanuvchi uchun. */
function Private({ children, adminOnly = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="boot">Yuklanmoqda…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/chat" replace />;
  return children;
}

/** Kirganlar login sahifasiga tushmasin. */
function Guest({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="boot">Yuklanmoqda…</div>;
  return user ? <Navigate to="/chat" replace /> : children;
}

export default function App() {
  return (
    <>
      <Aurora />
      <Routes>
        <Route path="/login" element={<Guest><Login /></Guest>} />
        <Route path="/signup" element={<Guest><Signup /></Guest>} />
        <Route path="/chat" element={<Private><Chat /></Private>} />
        <Route path="/models" element={<Private><Models /></Private>} />
        <Route path="/artifacts" element={<Private><Gallery /></Private>} />
        <Route path="/download" element={<Private><Download /></Private>} />
        <Route path="/admin" element={<Private adminOnly><Admin /></Private>} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
      <Toasts />
    </>
  );
}
