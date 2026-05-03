const backendOrigin =
  process.env.NEXT_INTERNAL_BACKEND_ORIGIN ||
  process.env.BACKEND_ORIGIN ||
  "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin.replace(/\/+$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
