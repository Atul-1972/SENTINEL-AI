import { useEffect, useRef, useState } from "react";
import { Download, Info, LoaderCircle, Search, X } from "lucide-react";
import { Badge, ClassBadge, EmptyState, RiskBadge } from "./ui";
import { api } from "../services/api";
import { download, percent, score, timestamp } from "../lib/format";

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  drawer = false,
}) {
  const ref = useRef();
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      dialog.close();
      previous?.focus();
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={drawer ? "modal flow-drawer" : "modal"}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal-inner">
        <div className="modal-header">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>
        {open && children}
      </div>
    </dialog>
  );
}

export default function FlowInspector({ predictionId, onClose }) {
  const [row, setRow] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  useEffect(() => {
    if (!predictionId) return;
    let active = true;
    setLoading(true);
    setError("");
    setRow(null);
    setQuery("");
    api
      .detail(predictionId)
      .then((result) => {
        if (active) setRow(result);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [predictionId]);
  return (
    <Modal
      open={!!predictionId}
      onClose={onClose}
      drawer
      title={`Flow FLW-${String(predictionId || "").padStart(5, "0")}`}
      description="Saved prediction details"
    >
      {loading ? (
        <div className="loading-state" role="status">
          <LoaderCircle className="spin" size={23} />
          Loading saved flow…
        </div>
      ) : error ? (
        <EmptyState title="Could not load this flow" description={error} />
      ) : (
        row && (
          <>
            <div className="drawer-badges">
              <ClassBadge value={row.predicted_class} />
              <RiskBadge level={row.risk_level} />
              <Badge>{row.source.replaceAll("_", " ")}</Badge>
            </div>
            <div className="drawer-metrics">
              <div>
                <span>Model probability</span>
                <strong>{percent(row.confidence)}</strong>
                <small>Uncalibrated</small>
              </div>
              <div>
                <span>Anomaly score</span>
                <strong>{score(row.anomaly_score)}</strong>
                <small>
                  {row.anomaly_flag ? "Anomaly flagged" : "Not flagged"}
                </small>
              </div>
              <div>
                <span>Risk priority</span>
                <strong>
                  {row.risk_score}
                  <small> / 100</small>
                </strong>
                <small>Rule-based score</small>
              </div>
            </div>
            <dl className="detail-list compact">
              <div>
                <dt>Submitted</dt>
                <dd>{timestamp(row.created_at)}</dd>
              </div>
              <div>
                <dt>Model version</dt>
                <dd className="mono">{row.model_version}</dd>
              </div>
              <div>
                <dt>Attack category</dt>
                <dd>Not assigned by binary model</dd>
              </div>
            </dl>
            <div className="feature-heading">
              <h3>Input features</h3>
              <span>{Object.keys(row.features).length} saved values</span>
            </div>
            <label className="search-field">
              <Search size={15} />
              <input
                aria-label="Search input features"
                placeholder="Find a feature…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <div className="feature-list">
              {Object.entries(row.features)
                .filter(([name]) =>
                  name.toLowerCase().includes(query.toLowerCase()),
                )
                .map(([name, value]) => (
                  <div key={name}>
                    <span>{name}</span>
                    <b className="mono" title={String(value)}>
                      {value == null
                        ? "null"
                        : new Intl.NumberFormat("en-IN", {
                            maximumFractionDigits: 6,
                          }).format(value)}
                    </b>
                  </div>
                ))}
            </div>
            <div className="drawer-footer">
              <p>
                <Info size={13} />
                These are recorded inputs; saved preprocessing handles null
                values.
              </p>
              <button
                className="button secondary"
                onClick={() =>
                  download(
                    JSON.stringify(row, null, 2),
                    `sentinel-flow-${row.id}.json`,
                  )
                }
              >
                <Download size={15} />
                Download flow JSON
              </button>
            </div>
          </>
        )
      )}
    </Modal>
  );
}
