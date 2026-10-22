import type { ReactNode } from "react"
import { Icon } from "./Icon"

export function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string
  value: string
  onChange?: (value: string) => void
  children: ReactNode
}) {
  return (
    <label className="select-wrap">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        onChange={(event) => onChange?.(event.target.value)}
        value={value}
      >
        {children}
      </select>
      <Icon name="chevron-down" size={15} />
    </label>
  )
}
