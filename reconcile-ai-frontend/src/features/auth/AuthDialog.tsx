import { useEffect, useState, type FormEvent } from "react"
import { Icon } from "../../components/ui/Icon"
import { authenticate, type AuthUser } from "../../services/apiClient"

export function AuthDialog({
  onClose,
  onAuthenticated,
}: {
  onClose: () => void
  onAuthenticated: (user: AuthUser) => void
}) {
  const [mode, setMode] = useState<"login" | "signup">("login")
  const [showPassword, setShowPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }

    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [onClose])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmitting(true)
    setError(null)
    const form = new FormData(event.currentTarget)
    try {
      const user = await authenticate(mode, {
        email: String(form.get("email") ?? ""),
        password: String(form.get("password") ?? ""),
        fullName: String(form.get("name") ?? ""),
      })
      onAuthenticated(user)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to authenticate. Please try again.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      className="auth-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <section
        aria-labelledby="auth-title"
        aria-modal="true"
        className="auth-dialog"
        role="dialog"
      >
        <header className="auth-brand">
          <div className="auth-brand__title">
            <span className="auth-brand__mark" aria-hidden="true">
              <Icon name="mapping" size={22} />
            </span>
            <strong>Reconcile AI</strong>
          </div>
          <p>Intelligent financial reconciliation</p>
        </header>

        <div className="auth-content">
          <h2 id="auth-title">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="auth-description">
            {mode === "login"
              ? "Sign in to access your reconciliation workspace."
              : "Sign up to get started with your reconciliation workspace."}
          </p>

          <div aria-label="Account access" className="auth-tabs" role="tablist">
            <button
              aria-selected={mode === "login"}
              className={
                mode === "login" ? "auth-tab auth-tab--active" : "auth-tab"
              }
              onClick={() => {
                setMode("login")
                setError(null)
              }}
              role="tab"
              type="button"
            >
              Log in
            </button>
            <button
              aria-selected={mode === "signup"}
              className={
                mode === "signup" ? "auth-tab auth-tab--active" : "auth-tab"
              }
              onClick={() => {
                setMode("signup")
                setError(null)
              }}
              role="tab"
              type="button"
            >
              Create account
            </button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "signup" && (
              <label className="auth-field">
                <span>Full name</span>
                <input
                  autoComplete="name"
                  name="name"
                  placeholder="Your name"
                  required
                />
              </label>
            )}
            <label className="auth-field">
              <span>Email address</span>
              <input
                autoComplete="email"
                name="email"
                placeholder="you@example.com"
                required
                type="email"
              />
            </label>
            <label className="auth-field">
              <span>Password</span>
              <span className="auth-password">
                <input
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  name="password"
                  placeholder="Enter your password"
                  required
                  type={showPassword ? "text" : "password"}
                />
                <button
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="auth-password__toggle"
                  onClick={() => setShowPassword((current) => !current)}
                  type="button"
                >
                  <svg
                    aria-hidden="true"
                    fill="none"
                    height="20"
                    viewBox="0 0 24 24"
                    width="20"
                  >
                    <path
                      d="M2.5 12s3.3-6 9.5-6 9.5 6 9.5 6-3.3 6-9.5 6-9.5-6-9.5-6Z"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.8"
                    />
                    <circle
                      cx="12"
                      cy="12"
                      r="2.6"
                      stroke="currentColor"
                      strokeWidth="1.8"
                    />
                  </svg>
                </button>
              </span>
            </label>
            <button
              className="auth-submit"
              disabled={isSubmitting}
              type="submit"
            >
              {isSubmitting
                ? mode === "login"
                  ? "Signing in..."
                  : "Creating account..."
                : mode === "login"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>
          {error && (
            <div className="auth-error" role="alert">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
