/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  serverExternalPackages: ['@copilotkit/runtime'],
};

export default nextConfig;
