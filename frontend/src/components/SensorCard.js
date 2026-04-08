export default function SensorCard({ label, value, unit }) {
    return (
      <div style={{ padding: 16, border: "1px solid #ccc", margin: 8 }}>
        <h3>{label}</h3>
        <p>{value} {unit}</p>
      </div>
    );
  }