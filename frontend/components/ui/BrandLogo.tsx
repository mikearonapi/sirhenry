/**
 * Full brand block: "Sir HENRY" heading + "Your AI financial advisor" subtitle.
 * Used on splash, login, and API-waiting screens. White text on dark backgrounds.
 */
export default function BrandLogo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <h1 className="text-white text-5xl md:text-6xl tracking-tight">
        <span
          className="italic font-light"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Sir
        </span>
        <span
          className="ml-[0.2em] tracking-wide font-extrabold"
          style={{ fontFamily: "var(--font-display)" }}
        >
          HENRY
        </span>
      </h1>
      <p
        className="mt-3 text-accent text-sm md:text-base font-medium tracking-wide"
        style={{ fontFamily: "var(--font-display)" }}
      >
        Your AI financial advisor
      </p>
    </div>
  );
}
