import { useState } from "react"
import API from "../api/api"
import { useNavigate, Link } from "react-router-dom"

export default function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)

  // 🔥 NEW STATE (added)
  const [error, setError] = useState("")

  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)

    // 🔥 Validation added (no removal)
    if (!email || !password) {
      setError("⚠️ Please enter email and password")
      setLoading(false)
      return
    }

    try {
      setError("")

      // 🔥 DEBUG LOG
      console.log("Attempting login with:", { email, password })

      const res = await API.post("/auth/login", { email, password })

      // 🔥 DEBUG RESPONSE
      console.log("LOGIN SUCCESS:", res.data)

      // ✅ EXISTING LINE (kept)
      localStorage.setItem("token", res.data.access_token)

      // 🔥 NEW: store extra user info
      localStorage.setItem("refresh_token", res.data.refresh_token)
      localStorage.setItem("user", JSON.stringify(res.data))

      // 🔥 EXTRA SAFETY CHECK
      if (!res.data.access_token) {
        throw new Error("No token received")
      }

      // 🔥 Slight delay for smoother UX (optional but nice)
      setTimeout(() => {
        navigate("/dashboard",{replace:true})
      }, 100)

    } catch (err) {
      console.log("LOGIN ERROR:", err.response?.data)

      // ✅ EXISTING ALERT (kept)
      alert(err.response?.data?.detail || "Login failed")

      // 🔥 NEW UI ERROR
      setError(err.response?.data?.detail || "Login failed")

    } finally {
      setLoading(false)
    }
  }

  return (
  <div style={styles.container}>
    <div style={styles.card}>

      {/*  HEADER */}
      <div style={styles.header}>
        <div style={styles.title}>SHIELDPAY</div>
        <div style={styles.subtitle}>
          AI-powered income protection for gig workers
        </div>
      </div>

      {/* 🔥 ERROR DISPLAY */}
      {error && <p style={styles.error}>{error}</p>}
        

        <form onSubmit={handleLogin}>
          <input
            type="text"
            placeholder="Email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value)
              setError("") // 🔥 clear error on typing
            }}
            style={styles.input}
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              setError("") // 🔥 clear error
            }}
            style={styles.input}
          />

          <button type="submit" style={styles.button} disabled={loading}>
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p style={{ marginTop: "15px", fontSize: "14px" }}>
          Don’t have an account?{" "}
          <Link to="/register" style={{ color: "#f59e0b" }}>
            Register
          </Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  container: {
    height: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    background: "linear-gradient(135deg, #020617, #0f172a, #1e293b)"
  },

  card: {
    background: "rgba(30, 41, 59, 0.85)",
    padding: "40px",
    borderRadius: "16px",
    width: "340px",
    backdropFilter: "blur(12px)",
    boxShadow: "0 10px 40px rgba(0,0,0,0.6)",
    color: "white"
  },

  header: {
    textAlign: "center",
    marginBottom: "20px"
  },

  title: {
    fontSize: "28px",
    fontWeight: "700",
    letterSpacing: "1px"
  },

  subtitle: {
    fontSize: "13px",
    color: "#94a3b8"
  },

  // 🔥 NEW ERROR STYLE
  error: {
    color: "#f87171",
    fontSize: "14px",
    marginBottom: "10px",
    textAlign: "center"
  },

  input: {
    width: "100%",
    padding: "12px",
    marginBottom: "15px",
    borderRadius: "8px",
    border: "1px solid #334155",
    background: "#020617",
    color: "white"
  },

  button: {
    width: "100%",
    padding: "12px",
    background: "#f59e0b",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "bold",
    opacity: 1
  }
}