import SirHenryBrand from "./SirHenryBrand";

export default function Footer() {
  return (
    <footer className="bg-[#0A0A0B] border-t border-[#27272A] py-10 px-6">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <SirHenryBrand className="text-white text-base font-bold" />
        <p className="text-[#6B7280] text-xs">
          &copy; {new Date().getFullYear()} Henry Financial, Inc. &middot; Not a licensed
          financial advisor.
        </p>
        <div className="flex items-center gap-5 text-xs text-[#6B7280]">
          <a href="#" className="hover:text-[#9CA3AF] transition-colors">
            Privacy
          </a>
          <a href="#" className="hover:text-[#9CA3AF] transition-colors">
            Terms
          </a>
          <a href="#" className="hover:text-[#9CA3AF] transition-colors">
            Security
          </a>
        </div>
      </div>
    </footer>
  );
}
