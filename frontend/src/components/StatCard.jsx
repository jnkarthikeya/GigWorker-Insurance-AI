export default function StatCard({ label, value, sub, color }) {
  return (
    <div className="card">
      <h4>{label}</h4>
      <h2>{value}</h2>
      <p>{sub}</p>
    </div>
  )
}