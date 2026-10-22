type RunState = "completed" | "pending" | "failed"

function getRunState(status?: string | null): RunState | null {
  if (!status || typeof status !== "string") return null
  const normalizedStatus = status.trim().toLowerCase()
  if (normalizedStatus === "completed") return "completed"
  if (
    normalizedStatus === "pending" ||
    normalizedStatus === "in progress" ||
    normalizedStatus === "processing" ||
    normalizedStatus === "needs review"
  ) {
    return "pending"
  }
  if (normalizedStatus === "failed") return "failed"
  return null
}

export function RunStatusIcon({ status }: { status?: string | null }) {
  if (!status || typeof status !== "string") {
    return null
  }
  const state = getRunState(status)
  const commonProps = {
    width: 24,
    height: 24,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };

  if (!state) {
    return <span className="run-status-icon__fallback">{status}</span>
  }

  return (
    <span
      aria-label={status}
      className={`run-status-icon run-status-icon--${state}`}
      role="img"
      title={status}
    >
      <svg {...commonProps}>
        {state === "completed" && (
          <>
            <path d="M17 6 9 17l-5-5" />
          </>
        )}
        {state === "pending" && (
          <>
            <path d="M12 6v8m0 4h.01" />
          </>
        )}
        {state === "failed" && (
          <>
            <path d="M18 6 6 18M6 6l12 12" />
          </>
        )}
      </svg>
    </span>
  )
}
