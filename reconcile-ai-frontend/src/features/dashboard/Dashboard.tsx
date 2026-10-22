import { useNavigate, Link } from "react-router-dom"
import { Button } from "../../components/ui/Button"
import { Icon } from "../../components/ui/Icon"
import type { IconName } from "../../types/icons"
import { PageHeader } from "../../components/ui/PageHeader"
import { RunStatusIcon } from "../../components/ui/RunStatusIcon"
import { recentRuns } from "./dashboardData"
import type { WorkspaceData } from "../../services/apiClient"

export function Dashboard({
  onNewRun,
  workspace,
}: {
  onNewRun?: () => void
  workspace?: WorkspaceData
}) {
  const navigate = useNavigate()
  const handleNewRun = () => {
    if (onNewRun) {
      onNewRun()
    } else {
      navigate("/reconciliations/new")
    }
  }
  const demoMetrics = [
    {
      label: "Total runs",
      value: "24",
      note: "8 this month",
      icon: "history" as IconName,
    },
    {
      label: "Matched transactions",
      value: "4,176",
      note: "98.4% match rate",
      icon: "audit" as IconName,
    },
    {
      label: "Pending reviews",
      value: "18",
      note: "$4,280.20 unmatched",
      icon: "file" as IconName,
      warning: true,
    },
    {
      label: "Entity mappings",
      value: "12",
      note: "3 updated recently",
      icon: "mapping" as IconName,
    },
  ]
  const metrics = workspace
    ? [
        {
          label: "Total runs",
          value: workspace.metrics.total_runs.toLocaleString(),
          note: "In your workspace",
          icon: "history" as IconName,
        },
        {
          label: "Matched transactions",
          value: workspace.metrics.matched_transactions.toLocaleString(),
          note: "Across your reconciliation runs",
          icon: "audit" as IconName,
        },
        {
          label: "Pending reviews",
          value: workspace.metrics.pending_reviews.toLocaleString(),
          note: "Awaiting your review",
          icon: "file" as IconName,
          warning: workspace.metrics.pending_reviews > 0,
        },
        {
          label: "Entity mappings",
          value: workspace.metrics.entity_mappings.toLocaleString(),
          note: "In your workspace",
          icon: "mapping" as IconName,
        },
      ]
    : demoMetrics
  const runs = workspace?.runs ?? recentRuns
  const activities = workspace?.audit_events ?? []

  return (
    <>
      <PageHeader
        action={
          <Button icon="plus" onClick={handleNewRun} variant="primary">
            New run
          </Button>
        }
        description="A summary of reconciliation performance and recent workspace activity."
        title="Dashboard"
      />

      <section className="metric-grid" aria-label="Reconciliation summary">
        {metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <span
              className={`metric-card__icon ${metric.warning ? "warning" : ""}`}
            >
              <Icon name={metric.icon} />
            </span>
            <span className="metric-card__label">{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.note}</small>
          </article>
        ))}
      </section>

      <div className="dashboard-grid">
        <section className="panel dashboard-runs">
          <div className="panel__header">
            <div>
              <h2>Recent reconciliation runs</h2>
              <p>Latest processing activity across your data sources</p>
            </div>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Bank File</th>
                  <th>Ledger File</th>
                  <th>Date</th>
                  <th className="numeric">Transactions</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 3).map((run) => (
                  <tr key={run.id}>
                    <td>
                      <Link
                        className="table-id"
                        style={{ textDecoration: "none", color: "inherit" }}
                        to={`/reconciliations/${encodeURIComponent(run.id)}`}
                      >
                        {run.bank_file || "—"}
                      </Link>
                    </td>
                    <td>
                      <Link
                        className="table-id"
                        style={{ textDecoration: "none", color: "inherit" }}
                        to={`/reconciliations/${encodeURIComponent(run.id)}`}
                      >
                        {run.ledger_file || "—"}
                      </Link>
                    </td>
                    <td>
                      {workspace
                        ? new Date(run.date).toLocaleDateString()
                        : run.date}
                    </td>
                    <td className="numeric tabular">
                      {typeof run.transactions === "number"
                        ? run.transactions.toLocaleString()
                        : run.transactions}
                    </td>
                    <td>
                      <RunStatusIcon status={run.status} />
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr>
                    <td className="empty-table" colSpan={5}>
                      No reconciliation runs yet. Start a new run to see your
                      results here.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel activity">
          <div className="panel__header">
            <div>
              <h2>Recent activity</h2>
              <p>Updates from your team</p>
            </div>
            <Button ariaLabel="Activity actions" icon="more" variant="icon" />
          </div>
          <div className="activity__list">
            {workspace ? (
              activities.length > 0 ? (
                activities.slice(0, 3).map((activity, index) => (
                  <div
                    className="activity__item"
                    key={`${activity.title}-${index}`}
                  >
                    <span
                      className={`activity__dot activity__dot--${activity.tone}`}
                    />
                    <div>
                      <p>
                        {activity.title}{" "}
                        {activity.run && <strong>{activity.run}</strong>}
                      </p>
                      <small>{new Date(activity.date).toLocaleString()}</small>
                    </div>
                  </div>
                ))
              ) : (
                <p className="empty-message">No recent activity yet.</p>
              )
            ) : (
              <>
                <div className="activity__item">
                  <span className="activity__dot activity__dot--success" />
                  <div>
                    <p>
                      Match approved in <strong>RUN-004</strong>
                    </p>
                    <small>Alex Morgan · 12 minutes ago</small>
                  </div>
                </div>
                <div className="activity__item">
                  <span className="activity__dot" />
                  <div>
                    <p>
                      Entity mapping <strong>Bank–Payment</strong> updated
                    </p>
                    <small>Alex Morgan · 34 minutes ago</small>
                  </div>
                </div>
                <div className="activity__item">
                  <span className="activity__dot activity__dot--warning" />
                  <div>
                    <p>
                      Review requested for <strong>RUN-003</strong>
                    </p>
                    <small>System · 2 hours ago</small>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </>
  )
}
