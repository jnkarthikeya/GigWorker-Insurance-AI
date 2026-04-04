export default function Sidebar({ onLogout, activePage }) {
  return (
    <div style={{
      width: 200,
      background: "#020617",
      color: "white",
      padding: 20,
      position: "fixed",
      height: "100vh"
    }}>
      <h3>ShieldPay</h3>

      <p style={{ marginTop: 20 }}>
        {activePage === "dashboard" ? "Dashboard" : ""}
      </p>

      <button onClick={onLogout} style={{ marginTop: 20 }}>
        Logout
      </button>
    </div>
  )
}