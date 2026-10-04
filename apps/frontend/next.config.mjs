/** @type {import('next').NextConfig} */
const nextConfig = {
  // standalone output is for the Docker image only (NEXT_STANDALONE=1); `next start` (e2e, local) needs it off
  output: process.env.NEXT_STANDALONE === "1" ? "standalone" : undefined,
  poweredByHeader: false,
  reactStrictMode: true,
};
export default nextConfig;
