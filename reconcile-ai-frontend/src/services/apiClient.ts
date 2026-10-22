interface UploadResponse {
  fileName: string
  validRows: number
  matchedCount: number
  pendingReviewCount: number
  exceptionCount: number
  unmatchedCount: number
}

export interface AuthUser {
  id: string
  full_name: string
  email: string
  is_active: boolean
  created_at: string
}

export interface WorkspaceRun {
  id: string
  date: string
  bank_file?: string
  ledger_file?: string
  transactions: number
  status: string
  tone: "success" | "warning" | "error" | "info" | "neutral"
}

export interface WorkspaceMapping {
  id: string
  original: string
  matched: string
  source: string
  confidence: string
  status: "Pending Review" | "Approved" | "Rejected"
}

export interface WorkspaceCandidateView {
  id: string
  ledger_entry_id?: string | null
  title?: string | null
  customer?: string | null
  ledger_value: string
  ledger_date?: string | null
  ledger_reference?: string | null
  invoice_reference?: string | null
  difference: string
  confidence?: number | null
  match_status?: string | null
  amount_diff_text?: string | null
  date_diff_text?: string | null
  entity_diff_text?: string | null
  ref_diff_text?: string | null
  suggestion?: string | null
  evidence?: string | null
  has_collision?: boolean
  collision_warning?: string | null
  competing_bank_transactions?: string[]
}

export interface WorkspaceException {
  id: string
  entity: string
  customer: string | null
  reason: string
  reason_type: string
  run: string
  status: "Pending Review" | "Approved" | "Rejected"
  bank_transaction_id: string | null
  ledger_entry_id: string | null
  bank_description: string | null
  bank_label: string
  bank_value: string
  ledger_label: string
  ledger_value: string
  difference: string
  bank_date: string | null
  ledger_date: string | null
  bank_reference: string | null
  ledger_reference: string | null
  invoice_reference: string | null
  suggestion: string | null
  explanation?: string | null
  ai_analyzed_at?: string | null
  candidates?: WorkspaceCandidateView[]
}

export interface WorkspaceAuditEvent {
  title: string
  action: string
  run: string
  resource: string
  description: string
  date: string
  tone: "success" | "warning" | "error" | "info" | "neutral"
  icon: "audit" | "mapping" | "upload" | "history"
}

export interface WorkspaceData {
  metrics: {
    total_runs: number
    matched_transactions: number
    pending_reviews: number
    entity_mappings: number
    audited_approved_exceptions?: number
  }
  runs: WorkspaceRun[]
  mappings: WorkspaceMapping[]
  exceptions: WorkspaceException[]
  audit_events: WorkspaceAuditEvent[]
}

export interface ValidatedReconciliation {
  run_id: string
  created_at: string
  bank_file_name: string
  ledger_file_name: string
  valid_rows: number
}

export interface ReconciliationOutcome {
  run_id: string
  matched_count: number
  pending_review_count: number
  exception_count: number
  unmatched_count: number
}

export interface ReconciliationDetailsResponse {
  run_id: string
  status: string
  created_at: string
  source_summary: string
  total_processed: number
  matched_count: number
  needs_review_count: number
  exception_count: number
  bank_file_name: string
  ledger_file_name: string
  date_window: string
  processing_time: string
  transactions: {
    id: string
    display_id: string
    reference: string | null
    entity: string
    amount_summary: string
    explanation: string
    status: "matched" | "review" | "exception" | "unmatched"
  }[]
}

interface AuthResponse {
  user: AuthUser
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function readResponse<T>(response: Response): Promise<T> {
  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    const errorPayload =
      typeof payload === "object" && payload !== null
        ? payload as Record<string, unknown>
        : {}
    const message =
      typeof errorPayload.detail === "string"
        ? errorPayload.detail
        : typeof errorPayload.message === "string"
          ? errorPayload.message
          : `Request failed (${response.status})`
    throw new ApiError(message, response.status)
  }

  return payload as T
}

function isReconciliationOutcome(
  payload: unknown,
): payload is ReconciliationOutcome {
  if (typeof payload !== "object" || payload === null) return false
  const outcome = payload as Record<string, unknown>
  return (
    typeof outcome.run_id === "string" &&
    typeof outcome.matched_count === "number" &&
    typeof outcome.pending_review_count === "number" &&
    typeof outcome.exception_count === "number" &&
    typeof outcome.unmatched_count === "number"
  )
}

export async function authenticate(
  mode: "login" | "signup",
  fields: { email: string; password: string; fullName?: string },
): Promise<AuthUser> {
  const endpoint =
    mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register"
  const body =
    mode === "login"
      ? { email: fields.email, password: fields.password }
      : {
          full_name: fields.fullName ?? "",
          email: fields.email,
          password: fields.password,
        }
  const response = await fetch(`${apiBaseUrl}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  })
  const payload = await readResponse<AuthResponse>(response)
  return payload.user
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/me`, {
    credentials: "include",
  })
  if (response.status === 401) return null
  return readResponse<AuthUser>(response)
}

export async function logout(): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/logout`, {
    method: "POST",
    credentials: "include",
  })
  if (!response.ok) await readResponse<void>(response)
}

export async function getWorkspace(): Promise<WorkspaceData> {
  const response = await fetch(`${apiBaseUrl}/api/v1/workspace`, {
    credentials: "include",
  })
  return readResponse<WorkspaceData>(response)
}

export async function getValidatedReconciliations(): Promise<ValidatedReconciliation[]> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/reconciliations/validated`,
    { credentials: "include" },
  )
  return readResponse<ValidatedReconciliation[]>(response)
}

export async function executeReconciliation(
  runId: string,
): Promise<ReconciliationOutcome> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/reconciliations/${encodeURIComponent(runId)}/execute`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({}),
    },
  )
  const payload = await readResponse<unknown>(response)
  if (!isReconciliationOutcome(payload)) {
    throw new Error("The server returned an invalid reconciliation result.")
  }
  return payload
}

export async function getReconciliationDetails(
  runId: string,
): Promise<ReconciliationDetailsResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/reconciliations/${encodeURIComponent(runId)}/details`,
    { credentials: "include" },
  )
  return readResponse<ReconciliationDetailsResponse>(response)
}

export interface AnalyzeExceptionResponse {
  exception_id: string
  explanation: string
  suggestion: string
  has_collision: boolean
  collision_warning: string | null
  competing_bank_transactions: string[]
  confidence?: string | null
}

export async function analyzeException(
  runId: string,
  exceptionId: string,
  candidateId?: string,
): Promise<AnalyzeExceptionResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/reconciliations/${encodeURIComponent(runId)}/exceptions/${encodeURIComponent(exceptionId)}/analyze`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ candidate_id: candidateId }),
    },
  )
  return readResponse<AnalyzeExceptionResponse>(response)
}

export async function reviewCandidate(
  runId: string,
  candidateId: string,
  action: "approve" | "reject" | "approved" | "rejected",
  comment?: string,
): Promise<{ candidate_id: string; status: string; message: string }> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/reconciliations/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ action, comment }),
    },
  )
  return readResponse(response)
}

function isUploadResponse(payload: unknown): payload is UploadResponse {
  if (typeof payload !== "object" || payload === null) return false
  const response = payload as Record<string, unknown>
  return (
    typeof response.fileName === "string" &&
    typeof response.validRows === "number" &&
    typeof response.matchedCount === "number" &&
    typeof response.pendingReviewCount === "number" &&
    typeof response.exceptionCount === "number" &&
    typeof response.unmatchedCount === "number"
  )
}

export async function postForm(
  endpoint: string,
  formData: FormData,
): Promise<UploadResponse> {
  const response = await fetch(`${apiBaseUrl}${endpoint}`, {
    method: "POST",
    credentials: "include",
    body: formData,
  })
  const payload = await readResponse<unknown>(response)

  if (!isUploadResponse(payload)) {
    throw new Error("The server returned an invalid upload response.")
  }

  return payload
}
