import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

export default function Policy() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    setVisible(true)
  }, [])

  return (
    <div style={styles.container}>
      <div style={{
        ...styles.card,
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0px)" : "translateY(30px)"
      }}>

        {/* HEADER */}
        <h1 style={styles.title}>📄 My Policy</h1>
        <p style={styles.subtitle}>
          Your income protection overview
        </p>

        {/* POLICY INFO */}
        <div style={styles.grid}>
          <Stat label="Coverage" value="₹5000/week" color="#10b981" />
          <Stat label="Claims Used" value="2 / 5" color="#f59e0b" />
          <Stat label="Monthly Limit" value="12 Claims" color="#3b82f6" />
          <Stat label="Status" value="Active" color="#22c55e" />
        </div>

        {/* HIGHLIGHT PANEL */}
        <div style={styles.highlight}>
          <p style={styles.highlightText}>
             Your policy adapts dynamically based on your activity and environmental risk.
          </p>
        </div>

        {/* BACK BUTTON */}
        <Link to="/dashboard" style={styles.button}>
          ← Back to Dashboard
        </Link>

      </div>
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div style={{
      ...styles.statCard,
      borderLeft: `4px solid ${color}`
    }}>
      <p style={styles.statLabel}>{label}</p>
      <p style={{ ...styles.statValue, color }}>{value}</p>
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
    width: "600px",
    padding: "40px",
    borderRadius: "20px",
    background: "rgba(30, 41, 59, 0.85)",
    backdropFilter: "blur(12px)",
    boxShadow: "0 20px 60px rgba(0,0,0,0.7)",
    color: "white",
    transition: "all 0.6s ease"
  },

  title: {
    fontSize: "32px",
    fontWeight: "800",
    marginBottom: "5px"
  },

  subtitle: {
    color: "#94a3b8",
    marginBottom: "25px"
  },

  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "15px",
    marginBottom: "25px"
  },

  statCard: {
    padding: "16px",
    borderRadius: "12px",
    background: "#020617",
    transition: "0.3s"
  },

  statLabel: {
    fontSize: "12px",
    color: "#94a3b8"
  },

  statValue: {
    fontSize: "20px",
    fontWeight: "700",
    marginTop: "5px"
  },

  highlight: {
    background: "linear-gradient(135deg, #1e293b, #0f172a)",
    padding: "15px",
    borderRadius: "12px",
    marginBottom: "25px",
    border: "1px solid #334155"
  },

  highlightText: {
    fontSize: "14px",
    color: "#cbd5f5"
  },

  button: {
    display: "inline-block",
    padding: "12px 20px",
    background: "#f59e0b",
    borderRadius: "10px",
    textDecoration: "none",
    color: "black",
    fontWeight: "bold",
    transition: "0.3s"
  }
}