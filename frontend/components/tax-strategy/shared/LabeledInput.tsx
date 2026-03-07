export default function LabeledInput({ label, value, onChange, type = "number", placeholder = "0" }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-text-secondary mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full text-sm border border-border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent"
      />
    </div>
  );
}
