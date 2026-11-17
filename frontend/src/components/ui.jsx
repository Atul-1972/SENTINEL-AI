import {
  Activity,
  ArrowUpRight,
  ChevronRight,
  CircleHelp,
  Download,
  Inbox,
} from "lucide-react";
import { number, percent, shortTime } from "../lib/format";

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  className = "",
}) {
  return (
    <span className={`badge badge-${tone} ${className}`}>
      {dot && <i className="status-dot" />}
      {children}
    </span>
  );
}

export function RiskBadge({ level }) {
  return (
    <Badge
      tone={level === "HIGH" ? "red" : level === "MEDIUM" ? "amber" : "green"}
      dot
    >
      {level?.toLowerCase() || "unknown"}
    </Badge>
  );
}

export function ClassBadge({ value }) {
  return (
    <span
      className={`class-label ${value === "ATTACK" ? "text-red" : "text-green"}`}
    >
      <i />
      {value === "ATTACK" ? "Attack" : "Benign"}
    </span>
  );
}

export function PageHeader({ eyebrow, title, description, children }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}

export function Panel({
  title,
  description,
  action,
  children,
  className = "",
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon = Activity,
  tone = "green",
}) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <div className={`metric-icon ${tone}`}>
          <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
        </div>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">
        <i className={`mini-dot ${tone}`} />
        {detail}
      </div>
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  description,
  icon: Icon = Inbox,
  action,
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={24} strokeWidth={1.5} />
      </div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

export function TooltipHelp({ text }) {
  return (
    <span className="help-icon" title={text} aria-label={text}>
      <CircleHelp size={13} />
    </span>
  );
}

export function PredictionTable({
  rows,
  onSelect,
  emptyDescription,
  showInputRow = false,
}) {
  if (!rows.length)
    return (
      <EmptyState
        title="No matching flows"
        description={
          emptyDescription || "Try another filter or analyze a traffic CSV."
        }
      />
    );
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>{showInputRow ? "CSV record / flow" : "Flow ID"}</th>
            <th>Classification</th>
            <th>Risk level</th>
            <th>
              Model probability{" "}
              <TooltipHelp text="Raw probability for the selected class. These values are not calibrated." />
            </th>
            <th>Anomaly</th>
            <th>Submitted</th>
            <th>
              <span className="sr-only">Details</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <span className="mono flow-id">
                  {showInputRow && row.input_row ? `#${row.input_row} · ` : ""}
                  FLW-{String(row.id).padStart(5, "0")}
                </span>
              </td>
              <td>
                <ClassBadge value={row.predicted_class} />
              </td>
              <td>
                <RiskBadge level={row.risk_level} />
              </td>
              <td>
                <div className="probability-cell">
                  <span className="mono">{percent(row.confidence, 1)}</span>
                  <div className="tiny-meter">
                    <i style={{ width: `${row.confidence * 100}%` }} />
                  </div>
                </div>
              </td>
              <td>
                <span className={row.anomaly_flag ? "text-amber" : "muted"}>
                  {row.anomaly_flag ? "Flagged" : "Not flagged"}
                </span>
              </td>
              <td className="muted mono">{shortTime(row.created_at)}</td>
              <td>
                <button
                  className="icon-button table-action"
                  aria-label={`Inspect flow ${row.id}`}
                  onClick={() => onSelect(row.id)}
                >
                  <ArrowUpRight size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AlertTable({ rows, onSelect }) {
  if (!rows.length)
    return (
      <EmptyState
        title="No alerts in submitted history"
        description="Medium- and high-risk predictions appear here after analysis."
      />
    );
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Alert ID</th>
            <th>Severity</th>
            <th>Finding</th>
            <th>Source</th>
            <th>Submitted</th>
            <th>
              <span className="sr-only">Details</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="mono flow-id">
                ALT-{String(row.id).padStart(5, "0")}
              </td>
              <td>
                <RiskBadge level={row.risk_level} />
              </td>
              <td>
                <div className="finding-cell">
                  <span>{row.message}</span>
                  <small className="mono muted">
                    FLW-{String(row.prediction_id).padStart(5, "0")}
                  </small>
                </div>
              </td>
              <td>
                <Badge>{row.source.replaceAll("_", " ")}</Badge>
              </td>
              <td className="mono muted">{shortTime(row.created_at)}</td>
              <td>
                <button
                  className="icon-button table-action"
                  aria-label={`Inspect alert ${row.id}`}
                  onClick={() => onSelect(row.prediction_id)}
                >
                  <ArrowUpRight size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SectionLink({ children, onClick }) {
  return (
    <button className="text-button" onClick={onClick}>
      {children}
      <ChevronRight size={15} />
    </button>
  );
}

export function TableFooter({ showing, total, label = "records", children }) {
  return (
    <div className="table-footer">
      <span>
        Showing <b>{number(showing)}</b>
        {total != null && (
          <>
            {" "}
            of <b>{number(total)}</b>
          </>
        )}{" "}
        {label}
      </span>
      {children}
    </div>
  );
}
