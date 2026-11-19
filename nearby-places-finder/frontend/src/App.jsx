import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./AuthContext";
import Login from "./pages/Login";
import MapPage from "./pages/MapPage";

// Wrapper: if not logged in, redirect to /login
function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="center">Loading…</div>;
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login mode="login" />} />
      <Route path="/register" element={user ? <Navigate to="/" replace /> : <Login mode="register" />} />
      <Route path="/" element={<RequireAuth><MapPage /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
