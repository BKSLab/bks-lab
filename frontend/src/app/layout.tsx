import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Suspense } from "react";

import { FocusManager } from "@/components/tracking/FocusManager";
import { themeInitScript } from "@/lib/theme";
import "./globals.css";

const inter = localFont({
  src: "../assets/fonts/InterVariable.woff2",
  weight: "100 900",
  style: "normal",
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = localFont({
  src: "../assets/fonts/JetBrainsMonoVariable.woff2",
  weight: "100 800",
  style: "normal",
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "BKS Lab — разработка, AI, проекты и идеи",
    template: "%s — BKS Lab",
  },
  description:
    "Личный сайт BKS Lab: проекты, статьи и заметки о современной разработке, управлении и искусственном интеллекте.",
  openGraph: {
    siteName: "BKS Lab",
    locale: "ru_RU",
    type: "website",
    images: [
      {
        url: "/og/bks-lab-default.jpg",
        width: 1200,
        height: 630,
        alt: "BKS Lab",
      },
    ],
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "32x32" },
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  manifest: "/site.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#f4f7f9",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ru"
      data-theme="light"
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrainsMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        {children}
        <Suspense fallback={null}>
          <FocusManager />
        </Suspense>
      </body>
    </html>
  );
}
