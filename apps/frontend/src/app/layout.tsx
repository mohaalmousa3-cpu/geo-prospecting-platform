import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Disclaimer } from "@/components/Disclaimer";

export const metadata: Metadata = {
  title: "geo-prospecting-platform",
  description: "Prospectivity and anomaly screening (V1: local/private use only)",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: "2rem auto", maxWidth: 1280 }}>
        {children}
        <Disclaimer />
      </body>
    </html>
  );
}
