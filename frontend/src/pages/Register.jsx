import { useState, useEffect } from "react"
import API from "../api/api"
import { useNavigate, Link } from "react-router-dom"

export default function Register() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const [name, setName] = useState("")
  const [city, setCity] = useState("")
  const [vehicleType, setVehicleType] = useState("")
  const [income, setIncome] = useState("")

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  // 🔥 NEW: Risk + Premium
  const [risk, setRisk] = useState(null)
  const [premium, setPremium] = useState(null)

  const navigate = useNavigate()

  // 🔥 LIVE CALCULATION LOGIC
  useEffect(() => {
    if (!vehicleType || !income) return

    let baseRisk = 0

    // vehicle risk
    if (vehicleType === "bike") baseRisk += 3
    else if (vehicleType === "scooter") baseRisk += 2
    else if (vehicleType === "car") baseRisk += 1
    else if (vehicleType === "auto") baseRisk += 2
    else if (vehicleType === "truck") baseRisk += 3

    // income risk
    const inc = Number(income)
    if (inc < 3000) baseRisk += 3
    else if (inc < 7000) baseRisk += 2
    else baseRisk += 1

    // city risk (simple simulation)
    if (city.toLowerCase().includes("bangalore")) baseRisk += 2
    else if (city.toLowerCase().includes("mumbai")) baseRisk += 3
    else baseRisk += 1

    // risk label
    let riskLevel = "Low"
    if (baseRisk >= 7) riskLevel = "High"
    else if (baseRisk >= 5) riskLevel = "Medium"

    setRisk(riskLevel)

    // premium formula
    const calculatedPremium = Math.round((baseRisk * 50) + (inc * 0.02))
    setPremium(calculatedPremium)

  }, [vehicleType, income, city])

  const handleRegister = async (e) => {
    e.preventDefault()

    if (!name || !email || !password || !city || !vehicleType || !income) {
      setError("⚠️ Please fill all fields")
      return
    }

    try {
      setLoading(true)
      setError("")

      await API.post("/auth/register", {
        name,
        email,
        password,
        city,
        vehicle_type: vehicleType,
        declared_weekly_income: Number(income)
      })

      alert("Registered successfully ✅")
      setTimeout(() => {
        navigate("/login", { replace: true })
      }, 100)

    } catch (err) {
      console.log(err.response?.data)
      setError(err.response?.data?.detail || "Registration failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Create Account</h1>

        {error && <p style={styles.error}>{error}</p>}

        <form onSubmit={handleRegister}>

          <input
            type="text"
            placeholder="Full Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={styles.input}
          />

          <input
            type="text"
            placeholder="City (e.g. Bangalore)"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            style={styles.input}
          />

          <select
            value={vehicleType}
            onChange={(e) => setVehicleType(e.target.value)}
            style={styles.input}
          >
            <option value="">🚗 Select Vehicle Type</option>
            <option value="bike">🏍️ Bike</option>
            <option value="car">🚘 Car</option>
            <option value="scooter">🛵 Scooter</option>
            <option value="auto">🛺 Auto</option>
            <option value="truck">🚚 Truck</option>
          </select>

          <input
            type="number"
            placeholder="Weekly Income (₹)"
            value={income}
            onChange={(e) => setIncome(e.target.value)}
            style={styles.input}
          />

          {/* 🔥 LIVE RISK DISPLAY */}
          {risk && (
            <div style={styles.riskBox}>
              <p>⚠️ Risk Level: <b>{risk}</b></p>
              <p>💰 Estimated Weekly Premium: ₹{premium}</p>
            </div>
          )}

          <input
            type="text"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={styles.input}
          />

          <input
            type="password"
            placeholder="Password (min 6 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
          />

          <button style={styles.button} disabled={loading}>
            {loading ? "Creating Account..." : "Register"}
          </button>
        </form>

        <p style={{ marginTop: "15px" }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: "#f59e0b" }}>
            Login
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
    borderRadius: "20px",
    width: "360px",
    color: "white",
    textAlign: "center",
    backdropFilter: "blur(12px)",
    boxShadow: "0 10px 40px rgba(0,0,0,0.5)"
  },

  title: {
    marginBottom: "20px",
    fontSize: "26px",
    fontWeight: "700"
  },

  error: {
    color: "#f87171",
    fontSize: "14px",
    marginBottom: "10px"
  },

  input: {
    width: "100%",
    padding: "12px",
    marginBottom: "15px",
    borderRadius: "10px",
    border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.05)",
    color: "white",
    outline: "none"
  },

  // 🔥 NEW STYLE
  riskBox: {
    background: "rgba(16,185,129,0.1)",
    border: "1px solid rgba(16,185,129,0.4)",
    padding: "12px",
    borderRadius: "10px",
    marginBottom: "15px",
    fontSize: "14px"
  },

  button: {
    width: "100%",
    padding: "12px",
    background: "linear-gradient(135deg, #10b981, #059669)",
    border: "none",
    borderRadius: "10px",
    cursor: "pointer",
    color: "white",
    fontWeight: "600"
  }
}