import type { ReactNode } from "react"

export function Status({
  children,
  tone = "neutral",
}: {
  children: ReactNode
  tone?: "success" | "info" | "warning" | "error" | "neutral"
}) {
  return <span className={`status status--${tone}`}>{children}</span>
}
