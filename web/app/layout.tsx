import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SRE Mission Control | AI-Powered Observability",
  description:
    "AI-powered SRE dashboard with Generative UI for traces, logs, and metrics analysis",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
