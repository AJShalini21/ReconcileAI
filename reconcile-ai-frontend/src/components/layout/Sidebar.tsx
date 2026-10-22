import { NavLink } from "react-router-dom"
import { Button } from "../ui/Button"
import { Icon } from "../ui/Icon"
import type { IconName } from "../../types/icons"
import type { Page } from "../../types/navigation"
import type { AuthUser } from "../../services/apiClient"

export interface NavItem {
  label: Page
  path: string
  icon: IconName
}

export const navItems: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: "dashboard" },
  { label: "New Reconciliation", path: "/reconciliations/new", icon: "plus" },
  // { label: "Entity Mappings", path: "/entity-mappings", icon: "mapping" },
  { label: "Exception Review", path: "/exceptions", icon: "file" },
  { label: "Run History", path: "/run-history", icon: "history" },
  { label: "Audit History", path: "/audit-history", icon: "audit" },
]

export function Sidebar({
  page,
  onNavigate,
  onLogout,
  onOpenAuth,
  open,
  onClose,
  user,
}: {
  page?: Page
  onNavigate?: (page: Page) => void
  onLogout: () => void
  onOpenAuth: () => void
  open: boolean
  onClose: () => void
  user: AuthUser | null
}) {
  return (
    <>
      <aside className={`sidebar ${open ? "sidebar--open" : ""}`}>
        <div className="brand">
          <NavLink
            className="brand__mark"
            to="/dashboard"
            onClick={onClose}
            aria-label="Reconcile AI Dashboard"
          >
            <span />
            <span />
          </NavLink>
          <NavLink
            to="/dashboard"
            onClick={onClose}
            style={{
              textDecoration: "none",
              color: "inherit",
              fontWeight: 600,
            }}
          >
            Reconcile AI
          </NavLink>
          <Button
            ariaLabel="Close navigation"
            icon="close"
            onClick={onClose}
            variant="icon"
          />
        </div>
        <nav className="nav" aria-label="Primary navigation">
          <p className="nav__label">Workspace</p>
          {navItems.map((item) => (
            <NavLink
              className={({ isActive }) =>
                `nav__item ${isActive ? "nav__item--active" : ""}`
              }
              key={item.path}
              onClick={onClose}
              to={item.path}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          {user ? (
            <div className="profile">
              <span className="avatar">
                {user.full_name
                  .split(/\s+/)
                  .slice(0, 2)
                  .map((part) => part[0]?.toUpperCase())
                  .join("")}
              </span>
              <span className="profile__text">
                <strong>{user.full_name}</strong>
                <small>{user.email}</small>
              </span>
              <Button
                ariaLabel="Log out"
                icon="logout"
                onClick={onLogout}
                variant="icon"
              />
            </div>
          ) : (
            <button
              className="sidebar-login"
              onClick={onOpenAuth}
              type="button"
            >
              Log in or create account
            </button>
          )}
        </div>
      </aside>
      {open && (
        <button
          aria-label="Close navigation"
          className="sidebar-overlay"
          onClick={onClose}
          type="button"
        />
      )}
    </>
  )
}
