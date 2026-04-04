import React from "react"

export default function EnvPanel({ env }) {
  if (!env) return null

  return (
    <div className="card">
      <h3>Environment</h3>
      <p>Rain: {env.rain_intensity}</p>
      <p>Demand: {env.demand_level}</p>
      <p>Pollution: {env.pollution_level}</p>
    </div>
  )
}