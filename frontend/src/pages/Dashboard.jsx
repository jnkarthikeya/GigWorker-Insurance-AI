// --------------------------- IMPORTS ---------------------------
import React, { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"

import Sidebar from "../components/Sidebar"

// ✅ REQUIRED IMPORTS (ADDED)
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line
} from "recharts"

import TrustGauge from "../components/TrustGauge"
import EnvPanel from "../components/EnvPanel"

// --------------------------- COMPONENT ---------------------------
export default function Dashboard() {

  const navigate = useNavigate()


// --------------------------- STATES ----------------
const [fraudAlert, setFraudAlert] = useState(null)
const wsRef = useRef(null)
const [claimResult, setClaimResult] = useState(null)
const [triggerLoading, setTriggerLoading] = useState(null)
const clearAuthTokens = () => {
  localStorage.removeItem("token")
  localStorage.removeItem("user")
}
 

const handleTrigger = async (type) => {
  try {
    setTriggerLoading(type)

    const token = localStorage.getItem("token")

    const res = await fetch("http://localhost:8000/trigger", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ trigger_type: type })
    })

    const data = await res.json()

    setClaimResult(data)

  } catch (err) {
    console.error("Trigger failed", err)
  } finally {
    setTriggerLoading(null)
  }
}

// ✅ SAFE DEFAULT STATES
const [u, setU] = useState({
  name: "Karthik",
  city: "Bangalore",
  vehicle_type: "Bike",
  trust_score: 78
})

const [eventFeed, setEventFeed] = useState([])
const [environment, setEnvironment] = useState(null)
const [mlConfidence, setMlConfidence] = useState(null)

// 🔥 NEW (ADDED)
const [mlTrend, setMlTrend] = useState([])

const [animatedIncome, setAnimatedIncome] = useState([
  { week: "W1", actual: 300 },
  { week: "W2", actual: 500 },
  { week: "W3", actual: 450 },
  { week: "W4", actual: 700 }
])

const [trust_history, setTrustHistory] = useState([
  { week: "W1", trust: 60 },
  { week: "W2", trust: 70 },
  { week: "W3", trust: 75 },
  { week: "W4", trust: 80 }
])

// ---------------- EFFECT ----------------
useEffect(() => {

  const token = localStorage.getItem("token")

  if (!token) {
    navigate("/login")
    return
  }

  const storedUser = localStorage.getItem("user")
  let userId = null

  if (storedUser) {
  try {
    const parsed = JSON.parse(storedUser)

    userId = parsed.user_id

    // 🔥 THIS IS THE FIX (PUT HERE ONLY)
    setU(prev => ({
      ...prev,
      name: parsed.name || prev.name,
      city: parsed.city || prev.city,
      vehicle_type: parsed.vehicle_type || prev.vehicle_type
    }))

  } catch (e) {
    console.error("User parse failed", e)
  }
}

  if (!userId) {
    console.warn("No userId found, skipping WS")
    return
  }

  const ws = new WebSocket(`ws://localhost:8000/ws/user/${userId}`)
  wsRef.current = ws

  ws.onopen = () => {
    console.log("✅ WS connected")
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)

      console.log("WS DATA:", msg)

      // 🌍 ENVIRONMENT UPDATE (ADDED)
      if (msg.type === "environment_update") {
        setEnvironment(msg.environment)
      }

      // 🤖 ML UPDATE
      if (msg.ml && msg.ml.probability !== undefined) {
        setMlConfidence({
          probability: msg.ml.probability,
          trigger: msg.ml.trigger_type,
          shouldTrigger: msg.ml.should_trigger
        })

        // 🔥 ML TREND GRAPH
        setMlTrend(prev => [
          ...prev.slice(-10),
          {
            time: `T${prev.length + 1}`,
            value: msg.ml.probability * 100
          }
        ])

        // 🔥 SOFT SYSTEM MOVEMENT (OPTIONAL — makes UI alive)
        setAnimatedIncome(prev => {
          const last = prev[prev.length - 1]?.actual || 400

          return [
            ...prev.slice(-6),
            {
              week: `W${prev.length + 1}`,
              actual: last * (0.98 + Math.random() * 0.04)
            }
          ]
        })
      }

      // 🚀 CLAIM EVENT (MAIN LOGIC)
      if (msg.type === "event_alert" && msg.claim) {

        const claim = msg.claim

        // TRUST
        setU(prev => ({
          ...prev,
          trust_score: claim.new_trust_score || prev.trust_score
        }))

        setTrustHistory(prev => [
          ...prev.slice(-6),
          {
            week: `W${prev.length + 1}`,
            trust: claim.new_trust_score || prev[prev.length - 1].trust
          }
        ])

        // INCOME
        setAnimatedIncome(prev => {
          const lastIncome = prev[prev.length - 1]?.actual || 400

          const newIncome = claim.predicted_income || lastIncome

          return [
            ...prev.slice(-6),
            {
              week: `W${prev.length + 1}`,
              actual: newIncome
            }
          ]
        })

        // EVENTS
        setEventFeed(prev => [
          {
            message: `⚡ AI Triggered: ${claim.trigger_type}`,
            time: new Date().toLocaleTimeString()
          },
          ...prev
        ])
      }

      // ⚠️ NORMAL ALERT (NO DUPLICATE)
      if (msg.type === "event_alert" && !msg.claim) {
        setFraudAlert(msg.message)

        setEventFeed(prev => [
          {
            message: msg.message,
            time: new Date().toLocaleTimeString()
          },
          ...prev.slice(0, 10)
        ])

        setTimeout(() => setFraudAlert(null), 4000)
      }

    } catch (err) {
      console.error("WS parse error", err)
    }
  }

  ws.onerror = (err) => {
    console.error("WS error", err)
  }

  ws.onclose = () => {
    console.log("❌ WS disconnected")
  }

  return () => {
    if (wsRef.current) {
      wsRef.current.close()
    }
  }

}, [navigate])
const TRIGGERS = [
  { type: "rainfall", name: "Rain Trigger", icon: "🌧️" },
  { type: "aqi", name: "AQI Trigger", icon: "🌫️" },
  { type: "traffic", name: "Traffic Trigger", icon: "🚗" }
]
// --------------------------- MAIN RETURN ---------------------------
return (
  <>
    {/* ─── GLOBAL STYLES ─── */}
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

      :root {
        --bg-deep:       #02060f;
        --bg-card:       rgba(10, 18, 35, 0.82);
        --bg-card-hover: rgba(14, 24, 46, 0.95);
        --border:        rgba(241, 159, 11, 0.13);
        --border-glow:   rgba(241, 159, 11, 0.35);
        --amber:         #f59e0b;
        --amber-dim:     rgba(245, 158, 11, 0.18);
        --emerald:       #10b981;
        --emerald-dim:   rgba(16, 185, 129, 0.15);
        --red-alert:     #ef4444;
        --text-primary:  #e8edf5;
        --text-muted:    rgba(180, 195, 220, 0.55);
        --text-label:    rgba(245, 158, 11, 0.75);
        --radius-card:   18px;
        --radius-btn:    12px;
        --font-display:  'Syne', sans-serif;
        --font-mono:     'DM Mono', monospace;
        --shadow-card:   0 8px 40px rgba(0,0,0,0.55), 0 1px 0 rgba(255,255,255,0.04) inset;
        --shadow-glow-a: 0 0 30px rgba(245,158,11,0.12);
        --shadow-glow-e: 0 0 30px rgba(16,185,129,0.12);
      }

      /* ── BACKGROUND CANVAS ── */
      .app-layout {
        background: var(--bg-deep);
        min-height: 100vh;
        position: relative;
        overflow-x: hidden;
        font-family: var(--font-display);
      }
      .app-layout::before {
        content: '';
        position: fixed;
        inset: 0;
        background:
          radial-gradient(ellipse 80% 50% at 20% 0%,  rgba(245,158,11,0.07) 0%, transparent 60%),
          radial-gradient(ellipse 60% 40% at 80% 90%, rgba(16,185,129,0.06) 0%, transparent 55%),
          radial-gradient(ellipse 50% 60% at 50% 50%, rgba(2,6,15,0.9) 0%,  transparent 100%);
        pointer-events: none;
        z-index: 0;
      }
      .app-layout::after {
        content: '';
        position: fixed;
        inset: 0;
        background-image:
          linear-gradient(rgba(245,158,11,0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(245,158,11,0.03) 1px, transparent 1px);
        background-size: 44px 44px;
        pointer-events: none;
        z-index: 0;
      }

      /* ── MAIN CONTENT ── */
      .main-content {
        position: relative;
        z-index: 1;
        padding: 36px 40px 60px;
        animation: fadeSlideIn 0.6s cubic-bezier(0.16,1,0.3,1) both;
      }

      /* ── CARDS ── */
      .card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius-card);
        padding: 24px;
        box-shadow: var(--shadow-card);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        transition: border-color 0.3s, box-shadow 0.3s, transform 0.3s;
        position: relative;
        overflow: hidden;
      }
      .card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(245,158,11,0.4), transparent);
      }
      .card:hover {
        border-color: var(--border-glow);
        box-shadow: var(--shadow-card), var(--shadow-glow-a);
        transform: translateY(-2px);
        background: var(--bg-card-hover);
      }

      /* ── CARD TITLES ── */
      .card-title {
        font-family: var(--font-display);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--text-label);
        margin: 0 0 18px;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .card-title::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, var(--border-glow), transparent);
      }

      /* ── HEADER ── */
      .flex-between { display: flex; align-items: center; justify-content: space-between; }
      .mb-20        { margin-bottom: 28px; }

      /* ── TYPOGRAPHY ── */
      h2 {
        font-family: var(--font-display);
        font-size: 28px;
        font-weight: 800;
        color: var(--text-primary);
        margin: 0 0 6px;
        letter-spacing: -0.02em;
        line-height: 1.15;
      }
      .text-amber { color: var(--amber); }
      .text-muted {
        font-family: var(--font-mono);
        font-size: 12px;
        color: var(--text-muted);
        letter-spacing: 0.06em;
        margin: 0;
      }

      /* ── LIVE EVENT FEED ITEMS ── */
      .event-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        border-radius: 10px;
        border: 1px solid rgba(245,158,11,0.08);
        background: rgba(245,158,11,0.04);
        margin-bottom: 8px;
        font-family: var(--font-mono);
        font-size: 12px;
        color: var(--text-primary);
        transition: background 0.2s, border-color 0.2s;
        animation: slideInLeft 0.4s cubic-bezier(0.16,1,0.3,1) both;
      }
      .event-item:hover {
        background: rgba(245,158,11,0.08);
        border-color: rgba(245,158,11,0.2);
      }
      .event-pulse {
        width: 6px; height: 6px;
        border-radius: 50%;
        background: var(--emerald);
        box-shadow: 0 0 8px var(--emerald);
        flex-shrink: 0;
        animation: pulse 2s ease-in-out infinite;
      }
      .event-time {
        margin-left: auto;
        font-size: 10px;
        color: var(--text-muted);
        letter-spacing: 0.04em;
      }

      /* ── TRIGGER BUTTONS ── */
      .trigger-btn {
        display: block;
        width: 100%;
        margin-bottom: 10px;
        padding: 12px 16px;
        border-radius: var(--radius-btn);
        border: 1px solid var(--border);
        background: linear-gradient(135deg, rgba(14,24,46,0.9), rgba(2,6,15,0.95));
        color: var(--text-primary);
        cursor: pointer;
        font-family: var(--font-display);
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-align: left;
        transition: border-color 0.25s, background 0.25s, box-shadow 0.25s, transform 0.15s;
        position: relative;
        overflow: hidden;
      }
      .trigger-btn::before {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(245,158,11,0.08), transparent);
        opacity: 0;
        transition: opacity 0.25s;
      }
      .trigger-btn:hover {
        border-color: var(--border-glow);
        box-shadow: 0 0 20px rgba(245,158,11,0.15), 0 4px 16px rgba(0,0,0,0.4);
        background: linear-gradient(135deg, rgba(20,32,60,0.95), rgba(8,15,30,0.98));
      }
      .trigger-btn:hover::before { opacity: 1; }
      .trigger-btn:active { transform: scale(0.97); }

      /* ── CLAIM RESULT ── */
      .claim-status {
        font-family: var(--font-mono);
        font-size: 13px;
        color: var(--text-primary);
        margin: 0 0 14px;
        letter-spacing: 0.04em;
      }
      .claim-close-btn {
        padding: 8px 20px;
        border-radius: 8px;
        border: 1px solid var(--border-glow);
        background: var(--amber-dim);
        color: var(--amber);
        font-family: var(--font-display);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.08em;
        cursor: pointer;
        transition: background 0.2s, box-shadow 0.2s;
      }
      .claim-close-btn:hover {
        background: rgba(245,158,11,0.28);
        box-shadow: 0 0 16px rgba(245,158,11,0.2);
      }

      /* ── ML CONFIDENCE BAR ── */
      .confidence-display {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-top: 8px;
      }
      .confidence-number {
        font-family: var(--font-mono);
        font-size: 32px;
        font-weight: 500;
        color: var(--emerald);
        letter-spacing: -0.03em;
        line-height: 1;
      }
      .confidence-bar-wrap {
        flex: 1;
        height: 4px;
        border-radius: 99px;
        background: rgba(255,255,255,0.07);
        overflow: hidden;
      }
      .confidence-bar-fill {
        height: 100%;
        border-radius: 99px;
        background: linear-gradient(90deg, var(--emerald), #34d399);
        box-shadow: 0 0 10px var(--emerald);
        transition: width 1s cubic-bezier(0.16,1,0.3,1);
      }

      /* ── STAGGER ANIMATIONS ── */
      .card-col-left  > .card:nth-child(1) { animation: fadeSlideIn 0.5s 0.1s cubic-bezier(0.16,1,0.3,1) both; }
      .card-col-left  > .card:nth-child(2) { animation: fadeSlideIn 0.5s 0.2s cubic-bezier(0.16,1,0.3,1) both; }
      .card-col-left  > .card:nth-child(3) { animation: fadeSlideIn 0.5s 0.3s cubic-bezier(0.16,1,0.3,1) both; }
      .card-col-right > .card:nth-child(1) { animation: fadeSlideIn 0.5s 0.15s cubic-bezier(0.16,1,0.3,1) both; }
      .card-col-right > .card:nth-child(2) { animation: fadeSlideIn 0.5s 0.25s cubic-bezier(0.16,1,0.3,1) both; }
      .card-col-right > .card:nth-child(3) { animation: fadeSlideIn 0.5s 0.35s cubic-bezier(0.16,1,0.3,1) both; }
      .card-col-right > .card:nth-child(4) { animation: fadeSlideIn 0.5s 0.45s cubic-bezier(0.16,1,0.3,1) both; }

      /* ── RECHARTS OVERRIDES ── */
      .recharts-cartesian-axis-tick-value { fill: rgba(180,195,220,0.45); font-family: var(--font-mono); font-size: 11px; }
      .recharts-tooltip-wrapper .recharts-default-tooltip {
        background: rgba(10,18,35,0.97) !important;
        border: 1px solid var(--border-glow) !important;
        border-radius: 10px !important;
        font-family: var(--font-mono) !important;
        font-size: 12px !important;
        color: var(--text-primary) !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
      }
      .recharts-cartesian-grid line { stroke: rgba(255,255,255,0.04); }

      /* ── KEYFRAMES ── */
      @keyframes fadeSlideIn {
        from { opacity: 0; transform: translateY(18px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-10px); }
        to   { opacity: 1; transform: translateX(0); }
      }
      @keyframes pulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 8px var(--emerald); }
        50%       { opacity: 0.4; box-shadow: 0 0 3px var(--emerald); }
      }
      @keyframes alertShake {
        0%,100% { transform: translateX(0); }
        20%,60% { transform: translateX(-4px); }
        40%,80% { transform: translateX(4px); }
      }
      @keyframes alertIn {
        from { opacity: 0; transform: translateX(30px) scale(0.95); }
        to   { opacity: 1; transform: translateX(0) scale(1); }
      }
      
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
`}</style>
    
                           
    
{/* ✅ SIDEBAR */}
<Sidebar
  onLogout={() => {
    clearAuthTokens()

    // 🔥 CLOSE WS CLEANLY
    if (wsRef.current) {
      wsRef.current.close()
    }

    navigate('/login')
  }}
  activePage="dashboard"
/>

<div className="app-layout">

  {/* ALERT */}
  {fraudAlert && (
    <div style={{
      position: 'fixed',
      top: 24,
      right: 24,
      background: 'rgba(239,68,68,0.15)',
      padding: 12,
      borderRadius: 10,
      color: '#fca5a5',
      zIndex: 9999,
      animation: 'alertIn 0.3s ease'
    }}>
      ⚡ {fraudAlert}
    </div>
  )}

  <main className="main-content">

    {/* HEADER */}
    <div className="flex-between mb-20">
      <div>
        <h2>
          Welcome back, <span className="text-amber">{u?.name}</span>
        </h2>
        <p className="text-muted">
          📍 {u?.city} · 🚗 {u?.vehicle_type}
        </p>
      </div>

      {/* ACTION BUTTONS */}
      <div style={{ display: "flex", gap: 10 }}>

        <button
          onClick={() => navigate("/policy")}
          className="trigger-btn"
          style={{ width: "auto", padding: "10px 16px" }}
        >
          📄 Policy
        </button>

        <button
          onClick={() => {
            clearAuthTokens()
            if (wsRef.current) wsRef.current.close()
            navigate("/login")
          }}
          className="trigger-btn"
          style={{
            width: "auto",
            padding: "10px 16px",
            borderColor: "rgba(239,68,68,0.4)",
            color: "#f87171"
          }}
        >
          🔓 Logout
        </button>

      </div>
    </div>

    {/* GRID */}
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>

      {/* LEFT */}
      <div className="card-col-left" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* INCOME */}
        <div className="card">
          <p className="card-title">📈 Income Trend</p>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={animatedIncome}>
              <XAxis dataKey="week" />
              <YAxis />
              <Tooltip />
              <Area
                dataKey="actual"
                stroke="#10b981"
                fill="#10b98122"
                strokeWidth={mlConfidence?.probability > 0.7 ? 4 : 2} // 🔥 spike effect
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* TRUST HISTORY */}
        <div className="card">
          <p className="card-title">🔐 Trust Score History</p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trust_history}>
              <XAxis dataKey="week" />
              <YAxis />
              <Tooltip />
              <Line
                dataKey="trust"
                stroke="#f59e0b"
                strokeWidth={mlConfidence?.probability > 0.7 ? 4 : 2} // 🔥 spike effect
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* 🤖 ML TREND GRAPH */}
        <div className="card">
          <p className="card-title">📊 ML Trend</p>

          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={mlTrend}>
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Line
                dataKey="value"
                stroke={
                  mlConfidence?.probability > 0.7
                    ? "#ef4444"
                    : mlConfidence?.probability > 0.4
                    ? "#f59e0b"
                    : "#22c55e"
                }
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* EVENTS */}
        <div className="card">
          <p className="card-title">⚡ Live Event Feed</p>

          {eventFeed?.length === 0 ? (
            <div style={{ textAlign: "center", opacity: 0.6 }}>
              <p style={{ fontSize: 24 }}>⚡</p>
              <p className="text-muted">
                No events yet — waiting for triggers...
              </p>
            </div>
          ) : (
            eventFeed.map((e, i) => (
              <div key={i} className="event-item">
                <span className="event-pulse" />
                <span>{e.message}</span>
                <span className="event-time">{e.time}</span>
              </div>
            ))
          )}
        </div>

      </div>

      {/* RIGHT */}
      <div className="card-col-right" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        <div className="card">
          <p className="card-title">🎯 Trust Score</p>
          <TrustGauge score={u?.trust_score || 75} />
        </div>

        <div className="card">
          <p className="card-title">⚙️ Triggers</p>

          {TRIGGERS.map(t => (
            <button
              key={t.type}
              onClick={() => handleTrigger(t.type)}
              className="trigger-btn"
            >
              {triggerLoading === t.type
                ? "⏳ Processing..."
                : `${t.icon} ${t.name}`}
            </button>
          ))}
        </div>

        
        <EnvPanel environment={environment} />



        {/* POLICY */}
        <div className="card">
          <p className="card-title">📄 Your Policy</p>
          <p className="text-muted">
            Coverage active for rainfall, AQI, and traffic disruptions.
          </p>

          <button
            className="trigger-btn"
            onClick={() => navigate("/policy")}
          >
            View Full Policy →
          </button>
        </div>

        {/* 🤖 ML CONFIDENCE (UNCHANGED BUT ENHANCED BAR) */}
        {mlConfidence && (
          <div className="card">
            <p className="card-title">🤖 AI Confidence</p>

            <div className="confidence-display">
              <div className="confidence-number">
                {(mlConfidence?.probability * 100).toFixed(0)}%
              </div>

              <div className="confidence-bar-wrap">
                <div
                  className="confidence-bar-fill"
                  style={{
                    width: `${mlConfidence?.probability * 100}%`,
                    background:
                      mlConfidence?.probability > 0.7
                        ? "#ef4444"
                        : mlConfidence?.probability > 0.4
                        ? "#f59e0b"
                        : "#22c55e"
                  }}
                />
              </div>
            </div>

            <div style={{ marginTop: 12, fontSize: 12, opacity: 0.85 }}>

              {mlConfidence.shouldTrigger ? (
                <div style={{ color: "#10b981" }}>
                  ⚡ High likelihood of <b>{mlConfidence.trigger}</b> trigger
                </div>
              ) : (
                <div style={{ color: "#94a3b8" }}>
                  No trigger predicted
                </div>
              )}

              <div style={{ marginTop: 6 }}>
                {mlConfidence?.probability > 0.7 && "🔥 Strong signal"}
                {mlConfidence?.probability > 0.4 && mlConfidence.probability <= 0.7 && "⚠️ Moderate signal"}
                {mlConfidence?.probability <= 0.4 && "🟢 Low risk"}
              </div>

            </div>
          </div>
        )}

      </div>

    </div>

    {/* CLAIM RESULT */}
    {claimResult && (
      <div className="card" style={{ marginTop: 24 }}>
        <p className="claim-status">{claimResult.status}</p>
        <button
          className="claim-close-btn"
          onClick={() => setClaimResult(null)}
        >
          DISMISS
        </button>
      </div>
    )}

  </main>
</div>
</>
)
}