import { useState } from "react";
import {
  Activity,
  Filter,
  Radar,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import {
  AlertTable,
  Badge,
  MetricCard,
  PageHeader,
  Panel,
  PredictionTable,
  TableFooter,
} from "../components/ui";
import { RiskDistribution } from "../components/charts";
import { number } from "../lib/format";

export default function Threats({ dashboard: d, onInspect }) {
  const [tab, setTab] = useState("alerts");
  const [filter, setFilter] = useState("ALL");
  const alerts = d.alerts.filter(
    (row) => filter === "ALL" || row.risk_level === filter,
  );
  const history = d.history.filter(
    (row) => filter === "ALL" || row.risk_level === filter,
  );
  return (
    <div className="page-enter">
      <PageHeader
        eyebrow="INVESTIGATE & UNDERSTAND"
        title="Threat analysis"
        description="Trace each finding back to a submitted flow."
      >
        <Badge tone="violet">Binary classification</Badge>
      </PageHeader>
      <div className="metrics-grid three">
        <MetricCard
          label="Classifier attacks"
          value={number(d.stats?.attack_flows)}
          detail="BENIGN / ATTACK decisions"
          icon={ShieldAlert}
          tone="red"
        />
        <MetricCard
          label="Anomaly flags"
          value={number(d.stats?.anomaly_flows)}
          detail="Independent unusualness signal"
          icon={Radar}
          tone="violet"
        />
        <MetricCard
          label="Needs review"
          value={number(d.stats?.suspicious_flows)}
          detail="Union of attacks and anomalies"
          icon={Activity}
          tone="amber"
        />
      </div>
      <div className="two-column">
        <Panel
          title="Risk distribution"
          description="Priority across stored predictions"
        >
          <RiskDistribution distribution={d.stats?.risk_distribution} />
          <div className="panel-note">
            Priority scores follow fixed rules; they are not probabilities.
          </div>
        </Panel>
        <Panel
          title="Understand the signals"
          description="Classification and anomaly detection have different roles"
        >
          <div className="signal-row">
            <div className="signal-icon red">
              <ShieldAlert size={19} />
            </div>
            <div>
              <strong>Classifier returned ATTACK</strong>
              <p>Always high priority, with or without an anomaly flag.</p>
            </div>
            <Badge tone="red">80–90</Badge>
          </div>
          <div className="signal-row">
            <div className="signal-icon amber">
              <Radar size={19} />
            </div>
            <div>
              <strong>BENIGN with an anomaly</strong>
              <p>An unusual pattern to inspect, not a named attack.</p>
            </div>
            <Badge tone="amber">40</Badge>
          </div>
          <div className="coverage-note">
            <ShieldCheck size={16} />
            <span>
              Training attack coverage:{" "}
              <b>
                {d.model?.training_attack_labels?.join(", ") || "Not available"}
              </b>
              . The classifier does not assign attack categories.
            </span>
          </div>
        </Panel>
      </div>
      <Panel
        title="Investigation queue"
        description="Recent records from persistent SQLite history"
        className="table-panel"
        action={
          <Badge>
            {tab === "alerts" ? "Latest 100 alerts" : "Latest 100 flows"}
          </Badge>
        }
      >
        <div className="table-toolbar">
          <div className="segmented">
            <button
              className={tab === "alerts" ? "selected" : ""}
              aria-pressed={tab === "alerts"}
              onClick={() => setTab("alerts")}
            >
              Security alerts
            </button>
            <button
              className={tab === "flows" ? "selected" : ""}
              aria-pressed={tab === "flows"}
              onClick={() => setTab("flows")}
            >
              Flow history
            </button>
          </div>
          <label className="inline-select">
            <Filter size={14} />
            <span className="sr-only">Filter risk level</span>
            <select
              aria-label="Filter risk level"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="ALL">All risk levels</option>
              <option value="HIGH">High risk</option>
              <option value="MEDIUM">Medium risk</option>
              <option value="LOW">Low risk</option>
            </select>
          </label>
        </div>
        {tab === "alerts" ? (
          <AlertTable rows={alerts} onSelect={onInspect} />
        ) : (
          <PredictionTable rows={history} onSelect={onInspect} />
        )}
        <TableFooter
          showing={tab === "alerts" ? alerts.length : history.length}
          label={tab === "alerts" ? "recent alerts" : "recent flows"}
        >
          <span>Open a record to inspect its features</span>
        </TableFooter>
      </Panel>
    </div>
  );
}
