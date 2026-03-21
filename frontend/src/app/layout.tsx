import "./globals.css";

export const metadata = {
  title: "NEXUS",
  description: "Self-hosted AI coding agent platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
