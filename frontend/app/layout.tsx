import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AutoDev — Self-Healing Codebase Agent",
  description: "AI-powered autonomous code analysis, refactoring, and PR automation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <style>{`
          @keyframes slideIn {
            from { opacity: 0; transform: translateY(12px); }
            to   { opacity: 1; transform: translateY(0); }
          }
          @keyframes spin {
            from { transform: rotate(0deg); }
            to   { transform: rotate(360deg); }
          }
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.45; }
          }
          * { box-sizing: border-box; }
          ::-webkit-scrollbar { width: 6px; }
          ::-webkit-scrollbar-track { background: #0a0e1a; }
          ::-webkit-scrollbar-thumb { background: #1e2a45; border-radius: 3px; }
        `}</style>
      </head>
      <body style={{ margin: 0, padding: 0 }}>{children}</body>
    </html>
  );
}