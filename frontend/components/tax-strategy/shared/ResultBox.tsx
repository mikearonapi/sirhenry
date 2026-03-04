export default function ResultBox({ label, value, color }: {
  label: string;
  value: string;
  color?: "green";
}) {
  return (
    <div className={`${color === "green" ? "bg-green-50" : "bg-stone-50"} rounded-lg p-4`}>
      <p className={`text-xs ${color === "green" ? "text-green-600" : "text-stone-500"} mb-1`}>{label}</p>
      <p className={`font-semibold font-mono tabular-nums ${color === "green" ? "text-green-700" : "text-stone-800"}`}>{value}</p>
    </div>
  );
}
