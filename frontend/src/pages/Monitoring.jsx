import {
  Activity,
  ArrowUpRight,
  Boxes,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  Database,
  FlaskConical,
  GitBranch,
  Layers3,
  Radar,
  RefreshCw,
  Server,
} from "lucide-react";
import { Badge, PageHeader, Panel } from "../components/ui";
import { download, number, percent } from "../lib/format";
import { API_TARGET } from "../services/api";

export default function Monitoring({ dashboard: d, navigate }) {
  const candidates = d.model?.comparison?.candidates || [];
  const services = [
    {
      name: "Inference API",
      icon: Server,
      state: d.health?.model_ready ? "Connected" : "Unavailable",
      ready: !!d.health?.model_ready,
      description: "Saved model and preprocessing served by FastAPI.",
    },
    {
      name: "Prediction storage",
      icon: Database,
      state: d.health?.database_ready ? "Connected" : "Unavailable",
      ready: !!d.health?.database_ready,
      description: "SQLite stores actual predictions, sources and alerts.",
    },
    {
      name: "Data drift · Evidently",
      icon: Radar,
      state: "Not configured",
      description:
        "Reference-versus-current distribution reports will appear after monitoring is integrated.",
    },
    {
      name: "Experiments · MLflow",
      icon: FlaskConical,
      state: "Not connected",
      description:
        "The saved comparison is available below; a tracking server is not connected.",
    },
    {
      name: "Orchestration · Airflow",
      icon: Boxes,
      state: "Not configured",
      description: "No scheduled training DAG or retraining job is connected.",
    },
    {
      name: "CI · GitHub Actions",
      icon: GitBranch,
      state: "Not connected",
      description:
        "The CI workflow is configured on GitHub; live run status is not connected to this dashboard.",
    },
  ];
  return (
    <div className="page-enter">
      <PageHeader
        eyebrow="OPERATIONS & REPRODUCIBILITY"
        title="MLOps monitoring"
        description="A transparent view of what is connected—and what comes next."
      >
        <a
          className="button secondary"
          href={`${API_TARGET}/docs`}
          target="_blank"
          rel="noreferrer"
        >
          API documentation
          <ArrowUpRight size={15} />
        </a>
      </PageHeader>
      <div className="mlops-summary">
        <div className="model-symbol">
          <Layers3 size={23} />
        </div>
        <div>
          <strong>{d.model?.model_version || "No model connected"}</strong>
          <p>
            Selected from saved validation results · final quality gate{" "}
            {d.model?.training?.eligible_for_api_demo
              ? "passed"
              : "unavailable"}
          </p>
        </div>
        <button className="text-button" onClick={() => navigate("performance")}>
          View evaluation
          <ArrowUpRight size={15} />
        </button>
      </div>
      <div className="pipeline-strip">
        {[
          ["Data preparation", "Saved splits"],
          ["Model comparison", "Validation selection"],
          ["Artifact export", "Verified reload"],
          [
            "Local inference",
            d.health?.model_ready ? "API connected" : "Unavailable",
          ],
        ].map(([name, detail], index) => (
          <div key={name}>
            <span
              className={`pipeline-number ${d.model && (index < 3 || d.health?.model_ready) ? "ready" : ""}`}
            >
              {d.model && (index < 3 || d.health?.model_ready) ? (
                <Check size={15} />
              ) : (
                index + 1
              )}
            </span>
            <div>
              <strong>{name}</strong>
              <small>{detail}</small>
            </div>
          </div>
        ))}
      </div>
      <div className="services-grid">
        {services.map((service) => (
          <Panel key={service.name} className="service-card">
            <div className="service-card-top">
              <div className={`service-icon ${service.ready ? "green" : ""}`}>
                <service.icon size={21} strokeWidth={1.5} />
              </div>
              <Badge
                tone={service.ready ? "green" : "neutral"}
                dot={service.ready}
              >
                {service.state}
              </Badge>
            </div>
            <h2>{service.name}</h2>
            <p>{service.description}</p>
          </Panel>
        ))}
      </div>
      <Panel
        title="Saved training candidates"
        description="Historical exports, not live MLflow runs"
        action={
          <button
            className="button secondary small"
            disabled={!candidates.length}
            onClick={() =>
              download(
                JSON.stringify(d.model.comparison, null, 2),
                "sentinel-model-comparison.json",
              )
            }
          >
            <ArrowUpRight size={14} />
            Export comparison
          </button>
        }
      >
        <div className="saved-runs">
          {candidates.length ? (
            candidates.map((row) => (
              <div className="saved-run" key={row.candidate}>
                <div className="run-icon">
                  <FlaskConical size={18} />
                </div>
                <div>
                  <strong>
                    {row.candidate === "xgboost"
                      ? "XGBoost baseline"
                      : "Random Forest baseline"}
                  </strong>
                  <small>
                    Validation set ·{" "}
                    {number(d.model?.evaluation?.validation?.validation_rows)}{" "}
                    records
                  </small>
                </div>
                <div className="run-score">
                  <span>Attack F1</span>
                  <b className="mono">{percent(row.attack_f1, 3)}</b>
                </div>
                <Badge tone={row.passes_quality_gate ? "green" : "red"}>
                  {row.passes_quality_gate ? "Gate passed" : "Gate failed"}
                </Badge>
              </div>
            ))
          ) : (
            <div className="panel-note">
              Connect the API to load the saved candidate report.
            </div>
          )}
        </div>
      </Panel>
      <div className="roadmap-note">
        <Clock3 size={19} />
        <div>
          <strong>Monitoring and retraining are the next integrations.</strong>
          <p>
            No live drift, retraining history, DVC version state or verified CI
            status is claimed here. Performance monitoring will require
            trustworthy true labels.
          </p>
        </div>
      </div>
    </div>
  );
}
