import Link from "next/link";

import { AoiWorkbench } from "@/components/AoiWorkbench";

export default function Home() {
  return (
    <main>
      <h1>geo-prospecting-platform</h1>
      <p>
        Phase 2: define and validate an Area of Interest. Local/private use only — no authentication
        in V1. <Link href="/status">Backend status</Link>
      </p>
      <AoiWorkbench />
    </main>
  );
}
