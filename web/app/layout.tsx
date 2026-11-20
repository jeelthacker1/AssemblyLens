import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "AssemblyLens | Assembly intelligence",
  description: "Live visual assembly assistance and human verification",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
