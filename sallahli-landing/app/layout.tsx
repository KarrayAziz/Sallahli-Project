import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "Sallahli – La correction d'examens réinventée par l'IA",
  description:
    "Sallahli utilise l'intelligence artificielle pour corriger les examens manuscrits instantanément : OCR, barèmes intelligents, rapports détaillés.",
  keywords: "correction examens, IA, OCR, barème, notes, enseignants, edtech",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem={false}
          disableTransitionOnChange={false}
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
