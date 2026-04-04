import { Routes, Route, Navigate } from "react-router-dom"
import { useState, useEffect } from "react"

import Dashboard from "./pages/Dashboard"
import Policy from "./pages/Policy"
import Register from "./pages/Register"
import Login from "./pages/Login"

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"))

  useEffect(() => {
    // 🔥 IMMEDIATE SYNC (ADDED)
    setToken(localStorage.getItem("token"))

    const interval = setInterval(() => {
      setToken(localStorage.getItem("token"))
    }, 500)

    // 🔥 LISTEN TO STORAGE CHANGES (ADDED)
    const handleStorage = () => {
      setToken(localStorage.getItem("token"))
    }
    window.addEventListener("storage", handleStorage)

    return () => {
      clearInterval(interval)
      window.removeEventListener("storage", handleStorage)
    }
  }, [])

  return (
    <Routes>

      {/* 🔥 ROOT ROUTE (ENHANCED WITH REPLACE) */}
      <Route
        path="/"
        element={
          token
            ? <Navigate to="/dashboard" replace />
            : <Navigate to="/login" replace />
        }
      />

      <Route path="/register" element={<Register />} />

      {/* 🔥 DASHBOARD ROUTE (ENHANCED) */}
      <Route
        path="/dashboard"
        element={
          token
            ? <Dashboard />
            : <Navigate to="/login" replace />
        }
      />

      <Route path="/policy" element={<Policy />} />

      <Route path="/login" element={<Login />} />

    </Routes>
  )
}

export default App