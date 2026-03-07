export default function ResultBox({ label, value, color }: {
  label: string;
  value: string;
  color?: "green";
}) {
  return (
    <div className={`${color === "green" ? "bg-green-50" : "bg-surface"} rounded-lg p-4`}>
      <p className={`text-xs ${color === "green" ? "text-green-600" : "text-text-muted"} mb-1`}>{label}</p>
      <p className={`font-semibold font-mono tabular-nums ${color === "green" ? "text-green-700" : "text-text-primary"}`}>{value}</p>
    </div>
  );
}
