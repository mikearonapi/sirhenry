export default function SirHenryBrand({ className = "" }: { className?: string }) {
  return (
    <span className={className}>
      <span
        className="italic font-light"
        style={{ fontFamily: "var(--font-display)" }}
      >
        Sir
      </span>
      <span className="ml-[0.15em] tracking-wide font-extrabold">HENRY</span>
    </span>
  );
}
