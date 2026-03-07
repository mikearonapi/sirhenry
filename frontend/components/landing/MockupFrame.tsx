interface MockupFrameProps {
  title: string;
  dark?: boolean;
  fadeBottom?: boolean;
  children: React.ReactNode;
}

export default function MockupFrame({ title, dark = true, fadeBottom = true, children }: MockupFrameProps) {
  const bg = dark ? "bg-[#141416]" : "bg-card";
  const border = dark ? "border-[#27272A]" : "border-[#E5E7EB]";
  const titleColor = dark ? "text-[#6B7280]" : "text-[#9CA3AF]";
  const fadeBg = dark ? "from-[#0A0A0B]" : "from-card";

  return (
    <div className={`relative rounded-xl border ${border} ${bg} shadow-2xl shadow-[#22C55E]/5 overflow-hidden`}>
      {/* Title bar */}
      <div className={`flex items-center gap-2 px-4 py-3 border-b ${border}`}>
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#EF4444]/60" />
          <div className="w-3 h-3 rounded-full bg-[#EAB308]/60" />
          <div className="w-3 h-3 rounded-full bg-[#22C55E]/60" />
        </div>
        <span className={`text-xs ${titleColor} ml-2`}>{title}</span>
      </div>

      {/* Content */}
      <div className="relative">
        <div className="p-4 sm:p-6">{children}</div>

        {/* Bottom fade */}
        {fadeBottom && (
          <div className={`absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t ${fadeBg}/80 to-transparent pointer-events-none`} />
        )}
      </div>
    </div>
  );
}
