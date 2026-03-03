interface Quote {
  quote: string;
  role: string;
  age: number;
  city: string;
  source: string;
}

const QUOTES: Quote[] = [
  {
    quote:
      "I wish I could just ask \u2018can I afford this house\u2019 and get a real answer based on my numbers \u2014 not a generic calculator.",
    role: "Senior Product Manager",
    age: 34,
    city: "Seattle",
    source: "r/HENRYfinance",
  },
  {
    quote:
      "I don\u2019t need someone to manage my money. I need someone to tell me if I\u2019m making the right decisions.",
    role: "Software Engineer",
    age: 31,
    city: "San Francisco",
    source: "r/HENRYfinance",
  },
  {
    quote:
      "I don\u2019t want another app that tells me I spent too much on restaurants. I want something that helps me figure out if I should max my 401(k) or pay off loans.",
    role: "Attorney",
    age: 38,
    city: "Chicago",
    source: "r/HENRYfinance",
  },
];

export default function VoicesSection() {
  return (
    <section id="community" className="bg-[#0A0A0B] py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-[#6B7280] text-center mb-4">
          From the HENRY community
        </p>
        <h2
          className="text-center font-bold text-[#F9FAFB] mb-4"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(1.75rem, 3.5vw, 2.25rem)",
          }}
        >
          You&apos;re not alone in this.
        </h2>
        <p className="text-center text-[#6B7280] text-sm max-w-xl mx-auto mb-16">
          184,000 members strong on r/HENRYfinance. These are the questions
          and frustrations they voice every day.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {QUOTES.map((q) => (
            <div
              key={q.quote}
              className="bg-[#141416] border border-[#27272A] rounded-xl p-7"
            >
              <p className="text-[#D1D5DB] text-sm leading-relaxed mb-5">
                &ldquo;{q.quote}&rdquo;
              </p>
              <div className="border-t border-[#27272A] pt-4">
                <p className="text-[#F9FAFB] text-sm font-medium">
                  {q.role}, {q.age}
                </p>
                <p className="text-[#6B7280] text-xs mt-0.5">
                  {q.city} &middot; {q.source}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-12 text-center">
          <p className="text-[#6B7280] text-sm">
            Join <span className="text-[#22C55E] font-semibold">500+</span> HENRYs
            on the waitlist building toward real wealth.
          </p>
        </div>
      </div>
    </section>
  );
}
