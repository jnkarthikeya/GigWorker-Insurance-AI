import React from "react"

export default function BehavioralPanel({ behavioral }) {
  if (!behavioral) return null

  return (
    <div className="card">
      <h3>Behavior Analysis</h3>

      <p>
        <strong>Score:</strong> {behavioral.behavior_score}
      </p>

      <p>
        <strong>Pattern:</strong> {behavioral.pattern || "Normal"}
      </p>

      <p>
        <strong>Risk:</strong>{" "}
        {behavioral.behavior_score < 40 ? "High" : behavioral.behavior_score < 70 ? "Medium" : "Low"}
      </p>
    </div>
  )
}