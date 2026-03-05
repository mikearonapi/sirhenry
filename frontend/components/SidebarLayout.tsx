"use client";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import AiChat from "@/components/AiChat";

export default function SidebarLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  // Full-height pages manage their own padding/layout
  const isFullHeight = pathname === "/sir-henry";

  return (
    <div className="min-h-screen bg-[#faf9f7]">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed top-4 left-4 z-10 p-2 bg-white rounded-lg shadow-md border border-stone-200 lg:hidden"
      >
        <Menu size={20} className="text-stone-700" />
      </button>
      <main className="lg:ml-60 min-h-screen transition-all duration-200">
        {isFullHeight ? children : (
          <div className="max-w-7xl mx-auto px-8 py-8">{children}</div>
        )}
      </main>
      <AiChat />
    </div>
  );
}
