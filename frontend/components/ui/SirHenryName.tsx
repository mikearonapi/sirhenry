/**
 * Renders "Sir HENRY" with consistent brand styling:
 * "Sir" in italic light Plus Jakarta Sans, "HENRY" in extrabold with tracking.
 * Use this for inline name references throughout the app.
 */
export default function SirHenryName({ className = "" }: { className?: string }) {
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
