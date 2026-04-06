import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — CQ Engine",
  description: "Trading terminal dashboard overview",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
