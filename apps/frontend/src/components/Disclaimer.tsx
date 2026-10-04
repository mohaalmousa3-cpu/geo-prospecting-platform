import { DISCLAIMER_D1 } from "@/lib/disclaimer";

export function Disclaimer() {
  return (
    <footer role="note" aria-label="Scientific disclaimer" style={{ marginTop: 32, fontSize: 14 }}>
      <strong>Scientific disclaimer (D-1). </strong>
      {DISCLAIMER_D1}
    </footer>
  );
}
