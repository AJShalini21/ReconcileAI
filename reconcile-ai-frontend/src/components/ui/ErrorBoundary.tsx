import React, { Component, type ErrorInfo, type ReactNode } from "react"
import { Button } from "./Button"

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught application error:", error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
    if (window.location.search) {
      window.location.href = window.location.pathname
    } else {
      window.location.reload()
    }
  }

  private handleGoHome = () => {
    this.setState({ hasError: false, error: null })
    window.location.href = "/"
  }

  public override render() {
    if (this.state.hasError) {
      return (
        <section
          className="workspace-state"
          role="alert"
          style={{
            maxWidth: "600px",
            margin: "64px auto",
            padding: "32px",
            textAlign: "center",
          }}
        >
          <h2 style={{ fontSize: "20px", marginBottom: "8px" }}>
            Something went wrong
          </h2>
          <p
            style={{
              color: "var(--text-muted)",
              marginBottom: "16px",
              fontSize: "14px",
            }}
          >
            An unexpected error occurred while displaying this page.
          </p>
          {this.state.error && (
            <pre
              style={{
                background: "var(--code-bg, #f3f4f6)",
                padding: "12px",
                borderRadius: "6px",
                fontSize: "12px",
                textAlign: "left",
                overflowX: "auto",
                marginBottom: "20px",
                color: "var(--error, #dc2626)",
              }}
            >
              {this.state.error.message}
            </pre>
          )}
          <div
            style={{
              display: "flex",
              gap: "12px",
              justifyContent: "center",
            }}
          >
            <Button onClick={this.handleReset} variant="secondary">
              Back to Overview
            </Button>
            <Button onClick={this.handleGoHome} variant="primary">
              Return to Dashboard
            </Button>
          </div>
        </section>
      )
    }

    return this.props.children
  }
}
