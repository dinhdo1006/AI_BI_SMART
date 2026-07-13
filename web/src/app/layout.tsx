import type { Metadata } from "next";
import { Bricolage_Grotesque, Fraunces, Manrope } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({
  variable: "--font-display",
  subsets: ["latin", "vietnamese"],
  weight: ["500", "600", "700", "800"],
});

const sans = Manrope({
  variable: "--font-sans",
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
});

const serif = Fraunces({
  variable: "--font-serif",
  subsets: ["latin", "vietnamese"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: "AI BI Smart",
  description:
    "Conversational analytics — hỏi tiếng Việt, nhận dashboard và bài phân tích.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="vi"
      className={`${display.variable} ${sans.variable} ${serif.variable} h-full`}
    >
      <body className="min-h-full antialiased">{children}</body>
    </html>
  );
}
