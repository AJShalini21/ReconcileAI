import { useEffect, useState } from "react"
import {
  Routes,
  Route,
  Navigate,
  Outlet,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom"
import { AppLayout } from "./components/layout/AppLayout"
import { AuditHistory } from "./features/history/AuditHistory"
import { Dashboard } from "./features/dashboard/Dashboard"
import { EntityMappings } from "./features/entity-mappings/EntityMappings"
import { ExceptionReview } from "./features/exceptions/ExceptionReview"
import { NewReconciliation } from "./features/reconciliation/NewReconciliation"
import {
  ReconciliationDetails,
  type ReconciliationDetailData,
} from "./features/reconciliation/ReconciliationDetails"
import { RunHistory } from "./features/history/RunHistory"
import { AuthDialog } from "./features/auth/AuthDialog"
import {
  ApiError,
  getCurrentUser,
  getReconciliationDetails,
  getWorkspace,
  logout,
  type AuthUser,
  type ReconciliationDetailsResponse,
  type WorkspaceData,
} from "./services/apiClient"

function createIllustrativeRunDetails(runId: string): ReconciliationDetailData {
  const statusByRunId: Record<string, ReconciliationDetailData["status"] | undefined> =
    {
      "RUN-001": "Failed",
      "RUN-003": "Needs review",
    }
  const status = statusByRunId[runId] ?? "Completed"
  const statusTone: ReconciliationDetailData["statusTone"] =
    status === "Failed"
      ? "error"
      : status === "Needs review"
        ? "warning"
        : "success"

  return {
    runId,
    status,
    statusTone,
    sourceSummary: "Bank Statement vs Company Ledger",
    createdAt: new Date(2026, 9, 20, 10, 42).toISOString(),
    totalProcessed: 1250,
    matchedCount: 1176,
    needsReviewCount: 32,
    exceptionCount: 42,
    bankFileName: "bank_october.csv",
    ledgerFileName: "ledger_october.csv",
    dateWindow: "Oct 1 – Oct 20, 2026",
    processingTime: "4.8 seconds",
    transactions: [
      {
        id: "TXN-1001",
        displayId: "TXN-1001",
        reference: "INV-2048",
        entity: "ABC Industries",
        amountSummary: "₹25,000",
        explanation: "Exact amount · Date within tolerance · Name matched",
        status: "matched",
      },
      {
        id: "TXN-1002",
        displayId: "TXN-1002",
        reference: "INV-2051",
        entity: "Global Traders",
        amountSummary: "₹9,500 vs ₹10,000",
        explanation: "Amount difference: ₹500 · Review required",
        status: "review",
      },
      {
        id: "TXN-1003",
        displayId: "TXN-1003",
        entity: "Payment received",
        amountSummary: "₹7,200",
        explanation: "No eligible ledger candidate found",
        status: "exception",
      },
    ],
  }
}

function mapReconciliationDetails(
  result: ReconciliationDetailsResponse,
): ReconciliationDetailData {
  const transactions = result.transactions.map((transaction) => ({
    id: transaction.id,
    displayId: transaction.display_id,
    reference: transaction.reference,
    entity: transaction.entity,
    amountSummary: transaction.amount_summary,
    explanation: transaction.explanation,
    status: transaction.status,
  }))
  const normalizedStatus = (result.status || "").toLowerCase()
  const statusTone: ReconciliationDetailData["statusTone"] =
    normalizedStatus === "completed"
      ? "success"
      : normalizedStatus === "failed"
        ? "error"
        : normalizedStatus === "in progress"
          ? "info"
          : normalizedStatus === "pending"
            ? "warning"
            : "neutral"
  return {
    runId: result.run_id,
    status: result.status,
    statusTone,
    sourceSummary: result.source_summary,
    createdAt: result.created_at,
    totalProcessed: transactions.length,
    matchedCount: transactions.filter(
      (transaction) => transaction.status === "matched",
    ).length,
    needsReviewCount: transactions.filter(
      (transaction) => transaction.status === "review",
    ).length,
    exceptionCount: transactions.filter((transaction) =>
      ["exception", "unmatched"].includes(transaction.status),
    ).length,
    bankFileName: result.bank_file_name,
    ledgerFileName: result.ledger_file_name,
    dateWindow: result.date_window,
    processingTime: result.processing_time,
    transactions,
  }
}

function ReconciliationDetailsPage({
  currentUser,
}: {
  currentUser: AuthUser | null
}) {
  const { runId = "" } = useParams<{ runId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(runId)
  const isDemo = searchParams.get("demo") === "true" || currentUser === null || !isUUID

  const [detailData, setDetailData] = useState<ReconciliationDetailData | null>(
    null,
  )
  const [loading, setLoading] = useState(!isDemo)
  const [error, setError] = useState<string | null>(null)
  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    if (isDemo) {
      setDetailData(createIllustrativeRunDetails(runId))
      setLoading(false)
      setError(null)
      return
    }

    let active = true
    setLoading(true)
    setError(null)
    getReconciliationDetails(runId)
      .then((result) => {
        if (!active) return
        setDetailData(mapReconciliationDetails(result))
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load reconciliation details.",
        )
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [runId, isDemo, reloadCount])

  const handleBack = () => {
    if (window.history.length > 1 && window.history.state?.idx > 0) {
      navigate(-1)
    } else {
      navigate("/run-history", { replace: true })
    }
  }

  if (isDemo) {
    return (
      <ReconciliationDetails
        data={detailData}
        notice="Illustrative demo data — these sample transaction records are not the results for this run."
        onBack={handleBack}
        runId={runId}
      />
    )
  }

  return (
    <ReconciliationDetails
      data={detailData}
      error={error}
      loading={loading}
      onBack={handleBack}
      onRetry={() => setReloadCount((c) => c + 1)}
      runId={runId}
    />
  )
}

function NavigateToRunDetails() {
  const { runId } = useParams<{ runId: string }>()
  return (
    <Navigate
      replace
      to={`/reconciliations/${encodeURIComponent(runId ?? "")}`}
    />
  )
}

function NotFoundFallback() {
  const navigate = useNavigate()
  return (
    <section className="workspace-state" role="alert">
      <h2>Page not found</h2>
      <p>The page you are looking for does not exist or has been moved.</p>
      <button
        className="workspace-retry"
        onClick={() => navigate("/dashboard", { replace: true })}
        type="button"
      >
        Go to Dashboard
      </button>
    </section>
  )
}

export default function App() {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState<string | null>(null)
  const [workspaceState, setWorkspaceState] = useState<{
    userId: string
    data: WorkspaceData
  } | null>(null)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [workspaceReload, setWorkspaceReload] = useState(0)

  useEffect(() => {
    let active = true
    getCurrentUser()
      .then((user) => {
        if (active) setCurrentUser(user)
      })
      .catch((error: unknown) => {
        if (active) {
          setAuthError(
            error instanceof Error
              ? error.message
              : "Unable to check your sign-in session.",
          )
        }
      })
      .finally(() => {
        if (active) setAuthLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!currentUser) {
      setWorkspaceState(null)
      setWorkspaceError(null)
      return
    }

    let active = true
    setWorkspaceError(null)
    getWorkspace()
      .then((data) => {
        if (active) setWorkspaceState({ userId: currentUser.id, data })
      })
      .catch((error: unknown) => {
        if (active) {
          setWorkspaceError(
            error instanceof Error
              ? error.message
              : "Unable to load your workspace.",
          )
        }
      })
    return () => {
      active = false
    }
  }, [currentUser, workspaceReload])

  const handleLogout = async () => {
    setAuthError(null)
    try {
      await logout()
      setCurrentUser(null)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setCurrentUser(null)
        return
      }
      setAuthError(
        error instanceof Error ? error.message : "Unable to log out.",
      )
    }
  }

  const userWorkspace =
    currentUser && workspaceState?.userId === currentUser.id
      ? workspaceState.data
      : undefined
  const hasWorkspaceForUser = Boolean(userWorkspace)
  const isLoadingWorkspace =
    authLoading || (!!currentUser && !hasWorkspaceForUser && !workspaceError)

  return (
    <>
      <Routes>
        <Route
          element={
            <AppLayout
              authError={authError}
              authLoading={authLoading}
              currentUser={currentUser}
              onLogout={handleLogout}
              onOpenAuth={() => setAuthOpen(true)}
              onSidebarOpenChange={setSidebarOpen}
              sidebarOpen={sidebarOpen}
            >
              {isLoadingWorkspace ? (
                <section className="workspace-state" aria-live="polite">
                  <h2>Loading your workspace</h2>
                  <p>Fetching your reconciliation data…</p>
                </section>
              ) : workspaceError && !hasWorkspaceForUser ? (
                <section className="workspace-state" role="alert">
                  <h2>Unable to load your workspace</h2>
                  <p>{workspaceError}</p>
                  <button
                    className="workspace-retry"
                    onClick={() => setWorkspaceReload((value) => value + 1)}
                    type="button"
                  >
                    Try again
                  </button>
                </section>
              ) : (
                <>
                  {workspaceError && (
                    <p className="auth-status-error" role="alert">
                      Workspace refresh failed: {workspaceError}
                    </p>
                  )}
                  <Outlet />
                </>
              )}
            </AppLayout>
          }
        >
          <Route element={<Navigate replace to="/dashboard" />} path="/" />
          <Route
            element={
              <Dashboard
                onNewRun={() => navigate("/reconciliations/new")}
                workspace={userWorkspace}
              />
            }
            path="/dashboard"
          />
          <Route
            element={
              currentUser ? (
                <NewReconciliation
                  onViewDetails={(runId) =>
                    navigate(`/reconciliations/${encodeURIComponent(runId)}`)
                  }
                  onWorkspaceChanged={() =>
                    setWorkspaceReload((value) => value + 1)
                  }
                />
              ) : (
                <section className="workspace-state">
                  <h2>Sign in to start a reconciliation</h2>
                  <p>
                    You can explore the public demo without an account. Sign in
                    to upload files and create reconciliations in your private
                    workspace.
                  </p>
                  <button
                    className="workspace-retry"
                    onClick={() => setAuthOpen(true)}
                    type="button"
                  >
                    Log in / Sign up
                  </button>
                </section>
              )
            }
            path="/reconciliations/new"
          />
          <Route
            element={<ReconciliationDetailsPage currentUser={currentUser} />}
            path="/reconciliations/:runId"
          />
          <Route
            element={<NavigateToRunDetails />}
            path="/run-history/:runId"
          />
          <Route
            element={<EntityMappings workspace={userWorkspace} />}
            path="/entity-mappings"
          />
          <Route
            element={
              <ExceptionReview
                onRefresh={() => setWorkspaceReload((count) => count + 1)}
                workspace={userWorkspace}
              />
            }
            path="/exceptions"
          />
          <Route
            element={
              <RunHistory
                onViewDetails={(runId) =>
                  navigate(
                    currentUser
                      ? `/reconciliations/${encodeURIComponent(runId)}`
                      : `/reconciliations/${encodeURIComponent(runId)}?demo=true`,
                  )
                }
                workspace={userWorkspace}
              />
            }
            path="/run-history"
          />
          <Route
            element={<AuditHistory workspace={userWorkspace} />}
            path="/audit-history"
          />
          <Route element={<NotFoundFallback />} path="*" />
        </Route>
      </Routes>
      {authOpen && (
        <AuthDialog
          onAuthenticated={(user) => {
            setCurrentUser(user)
            setAuthError(null)
            setAuthOpen(false)
          }}
          onClose={() => setAuthOpen(false)}
        />
      )}
    </>
  )
}
