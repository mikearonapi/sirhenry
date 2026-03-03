import SirHenryBrand from "./SirHenryBrand";
import WaitlistForm from "./WaitlistForm";

export default function WaitlistSection() {
  return (
    <section id="waitlist" className="bg-white py-28 px-6">
      <div className="max-w-xl mx-auto text-center">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#9CA3AF] mb-4">
          Early access &middot; Spring 2026
        </p>
        <h2
          className="font-extrabold text-[#111827] mb-3"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(2rem, 4vw, 2.75rem)",
          }}
        >
          Every knight was once a HENRY.
        </h2>
        <p className="text-[#4B5563] text-lg font-medium mb-3 max-w-md mx-auto">
          Get the clarity your income deserves.
        </p>
        <p className="text-[#6B7280] text-base leading-relaxed mb-3 max-w-md mx-auto">
          <SirHenryBrand className="text-[#111827]" /> launches Spring 2026.
          Join the waitlist and get early access — plus a personalized
          financial snapshot the moment we open doors.
        </p>
        <p className="text-[#9CA3AF] text-xs mb-10">
          No spam. Just one email when we&apos;re ready.
        </p>
        <WaitlistForm />
        <p className="text-[#9CA3AF] text-xs mt-5">
          No minimums. No commissions. Your data stays yours.
        </p>
      </div>
    </section>
  );
}
