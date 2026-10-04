import Link from "next/link";

import { StatusPanel } from "@/components/StatusPanel";

export default function StatusPage() {
  return (
    <main>
      <h1>Backend status</h1>
      <p>
        <Link href="/">← AOI workbench</Link>
      </p>
      <StatusPanel />
    </main>
  );
}
