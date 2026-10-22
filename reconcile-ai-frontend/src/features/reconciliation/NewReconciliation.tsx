import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "../../components/ui/Button"
import { Icon } from "../../components/ui/Icon"
import { PageHeader } from "../../components/ui/PageHeader"
import { RunStatusIcon } from "../../components/ui/RunStatusIcon"
import { Status } from "../../components/ui/Status"
import {
  executeReconciliation,
  getValidatedReconciliations,
  postForm,
  type ReconciliationOutcome,
  type ValidatedReconciliation,
} from "../../services/apiClient"
import { UploadBox } from "./UploadBox"

interface SampleDatasetOption {
  id: string
  title: string
  records: number
  badge: string
  bankPath: string
  ledgerPath: string
  bankFilename: string
  ledgerFilename: string
}

const sampleDatasets: SampleDatasetOption[] = [
  {
    id: "dataset-100",
    title: "Dataset 1",
    records: 100,
    badge: "100 records",
    bankPath: "/sample-data/dataset-100-bank.csv",
    ledgerPath: "/sample-data/dataset-100-ledger.csv",
    bankFilename: "dataset-100-bank.csv",
    ledgerFilename: "dataset-100-ledger.csv",
  },
  {
    id: "dataset-150",
    title: "Dataset 2",
    records: 150,
    badge: "150 records",
    bankPath: "/sample-data/dataset-150-bank.csv",
    ledgerPath: "/sample-data/dataset-150-ledger.csv",
    bankFilename: "dataset-150-bank.csv",
    ledgerFilename: "dataset-150-ledger.csv",
  },
  {
    id: "dataset-200",
    title: "Dataset 3",
    records: 200,
    badge: "200 records",
    bankPath: "/sample-data/dataset-200-bank.csv",
    ledgerPath: "/sample-data/dataset-200-ledger.csv",
    bankFilename: "dataset-200-bank.csv",
    ledgerFilename: "dataset-200-ledger.csv",
  },
]

export function NewReconciliation({
  onWorkspaceChanged,
  onViewDetails,
}: {
  onWorkspaceChanged?: () => void
  onViewDetails?: (runId: string) => void
}) {
  const navigate = useNavigate()
  const [firstFile, setFirstFile] = useState<File>()
  const [secondFile, setSecondFile] = useState<File>()
  const [validatedRuns, setValidatedRuns] = useState<ValidatedReconciliation[]>(
    [],
  )
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [latestOutcome, setLatestOutcome] =
    useState<ReconciliationOutcome | null>(null)
  const [uploadMessage, setUploadMessage] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [validatedRunsError, setValidatedRunsError] = useState<string | null>(
    null,
  )
  const [loadingDatasetId, setLoadingDatasetId] = useState<string | null>(null)
  const ready = Boolean(firstFile && secondFile)

  const handleUseDataset = async (dataset: SampleDatasetOption) => {
    setLoadingDatasetId(dataset.id)
    setUploadError(null)
    setUploadMessage(null)
    try {
      const [bankResponse, ledgerResponse] = await Promise.all([
        fetch(dataset.bankPath),
        fetch(dataset.ledgerPath),
      ])

      if (!bankResponse.ok || !ledgerResponse.ok) {
        throw new Error("Unable to load sample dataset files.")
      }

      const [bankBlob, ledgerBlob] = await Promise.all([
        bankResponse.blob(),
        ledgerResponse.blob(),
      ])

      const bankFile = new File([bankBlob], dataset.bankFilename, {
        type: "text/csv",
      })
      const ledgerFile = new File([ledgerBlob], dataset.ledgerFilename, {
        type: "text/csv",
      })

      setFirstFile(bankFile)
      setSecondFile(ledgerFile)
      setUploadMessage(
        `Loaded ${dataset.title} (${dataset.records} records). Click "Validate files" to proceed.`,
      )
      window.scrollTo({ top: 0, behavior: "smooth" })
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : "Failed to load sample dataset.",
      )
    } finally {
      setLoadingDatasetId(null)
    }
  }

  // Warn if user attempts to refresh with unsaved local file selection
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (firstFile || secondFile) {
        e.preventDefault()
        e.returnValue = ""
      }
    }
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [firstFile, secondFile])

  const refreshValidatedRuns = async () => {
    setLoadingRuns(true)
    setValidatedRunsError(null)
    try {
      const runs = await getValidatedReconciliations()
      setValidatedRuns(runs)
    } catch (error) {
      setValidatedRunsError(
        error instanceof Error
          ? error.message
          : "Unable to load validated files.",
      )
    } finally {
      setLoadingRuns(false)
    }
  }

  useEffect(() => {
    void refreshValidatedRuns()
  }, [])

  const validateFiles = async () => {
    if (!firstFile || !secondFile) {
      throw new Error("Choose both CSV files before continuing.")
    }

    const formData = new FormData()
    formData.append("bankFile", firstFile)
    formData.append("ledgerFile", secondFile)

    return postForm("/api/v1/reconciliations/validate", formData)
  }

  const handleValidateFiles = async () => {
    if (!firstFile || !secondFile) {
      return
    }

    setIsValidating(true)
    setUploadError(null)
    setUploadMessage(null)
    setLatestOutcome(null)

    try {
      const payload = await validateFiles()
      // Clear unsaved file state upon successful validation
      setFirstFile(undefined)
      setSecondFile(undefined)
      await refreshValidatedRuns()
      setUploadMessage(
        `Validation passed: ${payload.validRows} valid rows. Files are now saved on the server ready for reconciliation.`,
      )
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown validation error"
      setUploadError(message)
    } finally {
      setIsValidating(false)
    }
  }

  const handleRunReconciliation = async (runId: string) => {
    setRunningId(runId)
    setUploadError(null)
    setUploadMessage(null)
    setLatestOutcome(null)

    try {
      const payload = await executeReconciliation(runId)
      setValidatedRuns((runs) => runs.filter((run) => run.run_id !== runId))
      setLatestOutcome(payload)
      if (onWorkspaceChanged) {
        onWorkspaceChanged()
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown reconciliation error"
      setUploadError(message)
    } finally {
      setRunningId(null)
    }
  }

  const handleViewDetails = (runId: string) => {
    if (onViewDetails) {
      onViewDetails(runId)
    } else {
      navigate(`/reconciliations/${encodeURIComponent(runId)}`)
    }
  }

  return (
    <>
      <PageHeader
        description="Validate the CSV files first, then run a separate reconciliation job."
        title="New reconciliation"
      />
      <section className="panel form-panel">
        <div className="section-heading">
          <span className="step">1</span>
          <div>
            <h2>Upload CSV files</h2>
            <p>Files must include a header row and be no larger than 25 MB.</p>
          </div>
        </div>
        <div className="upload-grid">
          <UploadBox
            file={firstFile}
            label="Upload first CSV"
            onFile={setFirstFile}
          />
          <UploadBox
            file={secondFile}
            label="Upload second CSV"
            onFile={setSecondFile}
          />
        </div>
        <p
          className="upload-note"
          style={{
            fontSize: "12px",
            color: "var(--text-secondary)",
            marginTop: "8px",
          }}
        >
          Unsaved file selections are kept in local memory and are cleared on
          page refresh. Once validated, records are securely saved on the
          server.
        </p>

        <div className="validation-row">
          <div>
            <span className="field-label">Validation status</span>
            {ready ? (
              <Status tone="neutral">
                Files selected — validate to add them to the run list
              </Status>
            ) : (
              <Status tone="neutral">Pending file selection</Status>
            )}
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <Button
              disabled={!ready || isValidating}
              onClick={handleValidateFiles}
              variant="primary"
            >
              {isValidating ? "Validating..." : "Validate files"}
            </Button>
          </div>
        </div>
        {uploadMessage && (
          <div className="success-message" role="status">
            <Icon name="audit" size={17} />
            {uploadMessage}
          </div>
        )}
        {uploadError && (
          <div
            className="success-message"
            role="alert"
            style={{ background: "#fff2f2", color: "#8b1e1e" }}
          >
            <Icon name="close" size={17} />
            {uploadError}
          </div>
        )}
      </section>

      <section className="panel sample-data-panel">
        <div className="section-heading">
          <div>
            <h2>Try sample data</h2>
            <p>
              Choose a sample dataset to explore Reconcile AI using synthetic
              financial transactions.
            </p>
          </div>
        </div>

        <div className="sample-grid">
          {sampleDatasets.map((dataset) => (
            <article className="sample-card" key={dataset.id}>
              <div>
                <div className="sample-card__header">
                  <h3 className="sample-card__title">{dataset.title}</h3>
                  <span className="sample-card__badge">{dataset.badge}</span>
                </div>
                <div className="sample-card__records">
                  {dataset.records} records
                </div>
              </div>

              <div className="sample-card__actions">
                <Button
                  disabled={loadingDatasetId !== null || isValidating}
                  onClick={() => handleUseDataset(dataset)}
                  variant="primary"
                >
                  {loadingDatasetId === dataset.id
                    ? "Loading files..."
                    : "Use dataset"}
                </Button>
                <div className="sample-card__downloads">
                  <a
                    className="button button--secondary"
                    download={dataset.bankFilename}
                    href={dataset.bankPath}
                    title={`Download ${dataset.bankFilename}`}
                  >
                    ↓ Bank CSV
                  </a>
                  <a
                    className="button button--secondary"
                    download={dataset.ledgerFilename}
                    href={dataset.ledgerPath}
                    title={`Download ${dataset.ledgerFilename}`}
                  >
                    ↓ Ledger CSV
                  </a>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
      {latestOutcome && (
        <section className="panel reconciliation-result" aria-live="polite">
          <div className="panel__header">
            <div>
              <h2>Reconciliation completed</h2>
              <p>
                Results for run{" "}
                <strong className="table-id">{latestOutcome.run_id}</strong>
              </p>
            </div>
            <RunStatusIcon status="Completed" />
          </div>
          <div className="reconciliation-result__metrics">
            <div>
              <span>Matched</span>
              <strong>{latestOutcome.matched_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Pending review</span>
              <strong>
                {latestOutcome.pending_review_count.toLocaleString()}
              </strong>
            </div>
            <div>
              <span>Exceptions</span>
              <strong>{latestOutcome.exception_count.toLocaleString()}</strong>
            </div>
            <div>
              <span>Unmatched</span>
              <strong>{latestOutcome.unmatched_count.toLocaleString()}</strong>
            </div>
          </div>
          <div className="reconciliation-result__action">
            <Button
              onClick={() => handleViewDetails(latestOutcome.run_id)}
              variant="secondary"
            >
              View reconciliation details
            </Button>
          </div>
        </section>
      )}
      <section className="panel validated-runs-panel">
        <div className="panel__header">
          <div className="section-heading">
          <span className="step">2</span>
          <div>
            <h2>Validated files waiting to be reconciled</h2>
            <p>
              Run reconciliation for a validated file pair when you are ready.
            </p>
          </div>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Validated</th>
                <th>Bank file</th>
                <th>Ledger file</th>
                <th className="numeric">Valid rows</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {validatedRuns.map((run) => (
                <tr key={run.run_id}>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                  <td>{run.bank_file_name}</td>
                  <td>{run.ledger_file_name}</td>
                  <td className="numeric tabular">
                    {run.valid_rows.toLocaleString()}
                  </td>
                  <td>
                    <Button
                      disabled={runningId !== null}
                      icon="audit"
                      onClick={() => handleRunReconciliation(run.run_id)}
                      variant="primary"
                    >
                      {runningId === run.run_id
                        ? "Running..."
                        : "Reconcile"}
                    </Button>
                  </td>
                </tr>
              ))}
              {!loadingRuns && validatedRunsError && (
                <tr>
                  <td className="empty-table" colSpan={5}>
                    <p>{validatedRunsError}</p>
                    <Button onClick={refreshValidatedRuns} variant="secondary">
                      Retry
                    </Button>
                  </td>
                </tr>
              )}
              {!loadingRuns &&
                !validatedRunsError &&
                validatedRuns.length === 0 && (
                  <tr>
                    <td className="empty-table" colSpan={5}>
                      No validated file pairs are waiting to be reconciled.
                    </td>
                  </tr>
                )}
              {loadingRuns && (
                <tr>
                  <td className="empty-table" colSpan={5}>
                    Loading validated files…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
