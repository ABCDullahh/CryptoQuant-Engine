import Link from "next/link";

export default function NotFound() {
  return (
    <div
      className="flex min-h-screen items-center justify-center"
      style={{
        backgroundColor: "#0D0D0D",
        fontFamily: '"Inter", system-ui, sans-serif',
      }}
    >
      <div className="text-center max-w-md px-6">
        <p
          className="text-6xl font-bold mb-4"
          style={{
            color: "#00F0FF",
            fontFamily: '"JetBrains Mono", monospace',
          }}
        >
          404
        </p>

        <h1
          className="text-2xl font-semibold mb-2"
          style={{ color: "#E5E2E1" }}
        >
          Page Not Found
        </h1>

        <p
          className="text-sm mb-8"
          style={{ color: "#B9CACB" }}
        >
          The page you are looking for does not exist or has been moved.
        </p>

        <Link
          href="/"
          className="inline-flex items-center justify-center px-6 py-2.5 text-sm font-medium rounded-sm transition-colors"
          style={{
            backgroundColor: "#00F0FF",
            color: "#00363A",
          }}
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
