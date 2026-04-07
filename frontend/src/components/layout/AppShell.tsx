"use client";

import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import Header from "./Header";
import AuthGuard from "./AuthGuard";

const PUBLIC_PATHS = ["/", "/login"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.includes(pathname);

  if (isPublic) {
    return <>{children}</>;
  }

  return (
    <AuthGuard>
      <div className="flex h-screen overflow-hidden bg-background text-on-surface font-body selection:bg-primary-container selection:text-on-primary-fixed w-full">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          <Header />
          <main className="flex-1 overflow-y-auto bg-[#0D0D0D] scroll-smooth p-6">
            {children}
          </main>
        </div>

        {/* Mobile Bottom Nav */}
        <MobileNav />
      </div>
    </AuthGuard>
  );
}

function MobileNav() {
  const pathname = usePathname();
  const items = [
    { href: "/dashboard", label: "Home", icon: "LayoutDashboard" },
    { href: "/analytics", label: "Analytics", icon: "LineChart" },
    { href: "/wallet", label: "Wallet", icon: "Landmark" },
    { href: "/settings", label: "Settings", icon: "Settings" },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-[#131313] border-t border-[#2A2A2A]/10 flex items-center justify-around h-16 z-50">
      {items.map((item) => {
        const isActive = pathname === item.href;
        return (
          <a
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center gap-1 ${isActive ? "text-primary-container" : "text-[#E5E2E1]/60"}`}
          >
            <span className="w-5 h-5" />
            <span className="text-[9px] uppercase font-bold">{item.label}</span>
          </a>
        );
      })}
    </nav>
  );
}
