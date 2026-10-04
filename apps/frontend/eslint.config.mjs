import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    ignores: [
      "public/maplibre/**",
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "src/types/contracts.ts",
    ],
  },
];

export default config;
