"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      className="flex min-h-screen items-center justify-center"
      style={{
        backgroundColor: "#0D0D0D",
        fontFamily: '"Inter", system-ui, sans-serif',
      }}
    >
      <div className="text-center max-w-md px-6">
        <div
          className="inline-flex items-center justify-center w-16 h-16 rounded-sm mb-6"
          style={{ backgroundColor: "rgba(147, 0, 10, 0.15)" }}
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#FFB4AB"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>

        <h1
          className="text-2xl font-semibold mb-2"
          style={{
            color: "#E5E2E1",
            fontFamily: '"Inter", system-ui, sans-serif',
          }}
        >
          Something went wrong
        </h1>

        <p
          className="text-sm mb-8"
          style={{ color: "#B9CACB" }}
        >
          An unexpected error occurred. Please try again or contact support if
          the issue persists.
        </p>

        {error.digest && (
          <p
            className="text-xs mb-6"
            style={{
              color: "#849495",
              fontFamily: '"JetBrains Mono", monospace',
            }}
          >
            Error ID: {error.digest}
          </p>
        )}

        <button
          onClick={reset}
          className="inline-flex items-center justify-center px-6 py-2.5 text-sm font-medium rounded-sm transition-colors cursor-pointer"
          style={{
            backgroundColor: "#00F0FF",
            color: "#00363A",
            fontFamily: '"Inter", system-ui, sans-serif',
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor = "#00DBE9")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = "#00F0FF")
          }
        >
          Try again
        </button>
      </div>
    </div>
  );
}
