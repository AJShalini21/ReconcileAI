import type { ReactNode } from "react"
import { Outlet } from "react-router-dom"
import { Button } from "../ui/Button"
import { Sidebar } from "./Sidebar"
import type { Page } from "../../types/navigation"
import type { AuthUser } from "../../services/apiClient"

export function AppLayout({
  children,
  page,
  onNavigate,
  sidebarOpen,
  onSidebarOpenChange,
  onOpenAuth,
  currentUser,
  authLoading,
  authError,
  onLogout,
}: {
  children?: ReactNode
  page?: Page
  onNavigate?: (page: Page) => void
  sidebarOpen: boolean
  onSidebarOpenChange: (open: boolean) => void
  onOpenAuth: () => void
  currentUser: AuthUser | null
  authLoading: boolean
  authError: string | null
  onLogout: () => void
}) {
  return (
    <div className="app-shell">
      <Sidebar
        onClose={() => onSidebarOpenChange(false)}
        onNavigate={onNavigate}
        onLogout={onLogout}
        onOpenAuth={onOpenAuth}
        open={sidebarOpen}
        page={page}
        user={currentUser}
      />
      <main className="main">
        <div className="mobile-bar">
          <Button
            ariaLabel="Open navigation"
            icon="menu"
            onClick={() => onSidebarOpenChange(true)}
            variant="icon"
          />
          <span>Reconcile AI</span>
          {currentUser ? (
            <button
              className="auth-launcher auth-launcher--mobile"
              onClick={onLogout}
              type="button"
            >
              Log out
            </button>
          ) : (
            <button
              className="auth-launcher auth-launcher--mobile"
              disabled={authLoading}
              onClick={onOpenAuth}
              type="button"
            >
              {authLoading ? "Checking..." : "Log in / Sign up"}
            </button>
          )}
        </div>
        <div className="top-corner-action">
          {currentUser ? (
            <Button
              ariaLabel="Log out"
              icon="logout"
              onClick={onLogout}
              variant="secondary"
            >
              <span>Log out</span>
              <span className="top-corner-user"> · {currentUser.full_name}</span>
            </Button>
          ) : (
            <Button
              disabled={authLoading}
              icon="user"
              onClick={onOpenAuth}
              variant="secondary"
            >
              {authLoading ? "Checking session..." : "Log in / Sign up"}
            </Button>
          )}
        </div>
        {authError && (
          <p className="auth-status-error" role="alert">
            Session status: {authError}
          </p>
        )}
        <div className="content">{children ?? <Outlet />}</div>
      </main>
    </div>
  )
}
