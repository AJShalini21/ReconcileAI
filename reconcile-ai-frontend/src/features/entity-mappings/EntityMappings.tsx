import { useState } from "react"
import { Button } from "../../components/ui/Button"
import { PageHeader } from "../../components/ui/PageHeader"
import { Status } from "../../components/ui/Status"
import type { WorkspaceData } from "../../services/apiClient"

type MappingStatus = "Pending Review" | "Approved" | "Rejected"

const initialMappings = [
  {
    id: "MAP-001",
    original: "ABC Pvt Ltd",
    matched: "ABC Private Limited",
    source: "Bank",
    confidence: "94%",
    status: "Pending Review" as MappingStatus,
  },
  {
    id: "MAP-002",
    original: "Global Tech Sol.",
    matched: "Global Technologies Ltd",
    source: "Ledger",
    confidence: "89%",
    status: "Pending Review" as MappingStatus,
  },
  {
    id: "MAP-003",
    original: "Northstar Svcs",
    matched: "Northstar Services Inc.",
    source: "Bank",
    confidence: "86%",
    status: "Pending Review" as MappingStatus,
  },
  {
    id: "MAP-004",
    original: "Apex Retail Co",
    matched: "Apex Retail Company",
    source: "Ledger",
    confidence: "98%",
    status: "Approved" as MappingStatus,
  },
  {
    id: "MAP-005",
    original: "Orbit Logistics",
    matched: "Orbit Logistics Group",
    source: "Bank",
    confidence: "72%",
    status: "Rejected" as MappingStatus,
  },
]

function MappingStatusBadge({ status }: { status: MappingStatus }) {
  return (
    <Status
      tone={
        status === "Approved"
          ? "success"
          : status === "Rejected"
            ? "error"
            : "warning"
      }
    >
      {status}
    </Status>
  )
}

export function EntityMappings({ workspace }: { workspace?: WorkspaceData }) {
  const [mappings, setMappings] = useState(initialMappings)
  const displayedMappings = workspace?.mappings ?? mappings

  const updateMapping = (id: string, status: MappingStatus) => {
    setMappings((current) =>
      current.map((mapping) =>
        mapping.id === id ? { ...mapping, status } : mapping,
      ),
    )
  }

  const pending = displayedMappings.filter(
    (mapping) => mapping.status === "Pending Review",
  )

  return (
    <>
      <PageHeader
        action={<Status tone="warning">{pending.length} pending</Status>}
        description="Review customer name variations identified during reconciliation."
        title="Entity mappings"
      />

      {pending.length > 0 && (
        <section className="pending-mapping-grid" aria-label="Pending mappings">
          {pending.slice(0, 3).map((mapping) => (
            <article className="pending-mapping-card" key={mapping.id}>
              <div className="pending-mapping-card__top">
                <span className="table-id">{mapping.id}</span>
                <MappingStatusBadge status={mapping.status} />
              </div>
              <div className="mapping-comparison">
                <div>
                  <small>Original name</small>
                  <strong>{mapping.original}</strong>
                </div>
                <span className="mapping-arrow">→</span>
                <div>
                  <small>Matched entity</small>
                  <strong>{mapping.matched}</strong>
                </div>
              </div>
              <div className="mapping-meta">
                <span>
                  {mapping.source} · {mapping.confidence} confidence
                </span>
              </div>
              {!workspace && (
                <div className="mapping-card-actions">
                  <Button
                    icon="close"
                    onClick={() => updateMapping(mapping.id, "Rejected")}
                  >
                    Reject
                  </Button>
                  <Button
                    icon="audit"
                    onClick={() => updateMapping(mapping.id, "Approved")}
                    variant="primary"
                  >
                    Approve
                  </Button>
                </div>
              )}
            </article>
          ))}
        </section>
      )}

      <section className="panel">
        <div className="panel__header">
          <div>
            <h2>All entity mappings</h2>
            <p>
              Canonical entity matches created across bank and ledger sources.
            </p>
          </div>
        </div>
        <div className="table-scroll">
          <table className="mapping-table">
            <thead>
              <tr>
                <th>Mapping ID</th>
                <th>Original Name</th>
                <th>Matched Entity Name</th>
                <th>Source</th>
                <th className="numeric">Match Confidence</th>
                <th>Status</th>
                {!workspace && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {displayedMappings.map((mapping) => (
                <tr key={mapping.id}>
                  <td>
                    <strong className="table-id">{mapping.id}</strong>
                  </td>
                  <td>{mapping.original}</td>
                  <td>{mapping.matched}</td>
                  <td>{mapping.source}</td>
                  <td className="numeric tabular">{mapping.confidence}</td>
                  <td>
                    <MappingStatusBadge status={mapping.status} />
                  </td>
                  {!workspace && (
                    <td>
                      <div className="inline-actions">
                        <Button variant="tertiary">View</Button>
                        {mapping.status === "Pending Review" && (
                          <>
                            <Button
        
                              onClick={() =>
                                updateMapping(mapping.id, "Approved")
                              }
                              variant="tertiary"
                            >
                              Approve
                            </Button>
                            <Button
                              onClick={() =>
                                updateMapping(mapping.id, "Rejected")
                              }
                              variant="tertiary"
                            >
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {displayedMappings.length === 0 && (
                <tr>
                  <td className="empty-table" colSpan={workspace ? 6 : 7}>
                    No entity mappings yet. Mappings will appear as your
                    reconciliation data is processed.
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
