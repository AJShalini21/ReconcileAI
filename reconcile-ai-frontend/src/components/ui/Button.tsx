import type { ReactNode } from "react"
import { Icon } from "./Icon"
import type { IconName } from "../../types/icons"

export function Button({
  children,
  icon,
  variant = "secondary",
  onClick,
  disabled,
  type = "button",
  ariaLabel,
}: {
  children?: ReactNode
  icon?: IconName
  variant?: "primary" | "secondary" | "tertiary" | "icon" | "danger" | "success" | "fail"
  onClick?: () => void
  disabled?: boolean
  type?: "button" | "submit"
  ariaLabel?: string
}) {
  return (
    <button
      aria-label={ariaLabel}
      className={`button button--${variant}`}
      disabled={disabled}
      onClick={onClick}
      type={type}
    >
      {icon && <Icon name={icon} size={16} />}
      {children}
    </button>
  )
}
