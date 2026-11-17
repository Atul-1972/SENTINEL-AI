import { useState } from "react";
import {
  CheckCircle2,
  Crosshair,
  Database,
  GitBranch,
  Layers3,
  Scale,
  ShieldCheck,
  Target,
  Timer,
  Trophy,
} from "lucide-react";
import {
  Badge,
  EmptyState,
  MetricCard,
  PageHeader,
  Panel,
} from "../components/ui";
import { bytes, number, percent } from "../lib/format";

export default function Performance({ dashboard: d }) {
  const [split, setSplit] = useState("test");
  const model = d.model;
  const metrics = model?.evaluation?.[split];
  const matrix = metrics?.confusion_matrix;
  const comparison = model?.comparison;
  return (
    <div className="page-enter">
      <PageHeader
        eyebrow="MEASURED, NOT ASSUMED"
        title="Model performance"
        description="Saved evaluation from your trained intrusion classifier."
      >
        <div className="segmented">
          <button
            className={split === "test" ? "selected" : ""}
            aria-pressed={split === "test"}
            onClick={() => setSplit("test")}
          >
            Final test
          </button>
          <button
            className={split === "validation" ? "selected" : ""}
            aria-pressed={split === "validation"}
            onClick={() => setSplit("validation")}
          >
            Validation
          </button>
        </div>
      </PageHeader>
      {!model ? (
        <Panel>
          <EmptyState
            title="Model report unavailable"
            description="Connect the API to read the saved evaluation artifacts."
          />
        </Panel>
      ) : (
        <>
          <div className="model-banner">
            <div className="model-symbol">
              <Layers3 size={25} />
            </div>
            <div>
              <div className="model-banner-title">
                <strong>
                  {model.active_model === "xgboost"
                    ? "XGBoost"
                    : "Random Forest"}
                </strong>
                <Badge tone="green" dot>
                  Active classifier
                </Badge>
              </div>
              <p className="mono">{model.model_version}</p>
            </div>
            <div className="model-banner-end">
              <CheckCircle2 size={16} />
              <span>Fixed quality gate passed</span>
            </div>
          </div>
          <div className="metrics-grid">
            <MetricCard
              label="Accuracy"
              value={percent(metrics?.accuracy)}
              detail={`${number(metrics?.test_rows || metrics?.validation_rows)} ${split} records`}
              icon={Target}
            />
            <MetricCard
              label="Attack precision"
              value={percent(metrics?.attack_precision)}
              detail="Correct among ATTACK predictions"
              icon={Crosshair}
              tone="blue"
            />
            <MetricCard
              label="Attack recall"
              value={percent(metrics?.attack_recall)}
              detail="Detected among labeled attacks"
              icon={ShieldCheck}
              tone="violet"
            />
            <MetricCard
              label="Attack F1"
              value={percent(metrics?.attack_f1)}
              detail="Balance of precision and recall"
              icon={Scale}
              tone="amber"
            />
          </div>
          <div className="performance-grid">
            <Panel
              title="Confusion matrix"
              description="Rows: actual class · columns: predicted class"
              action={
                <Badge>
                  {split === "test" ? "Reserved test split" : "Selection split"}
                </Badge>
              }
            >
              {matrix ? (
                <div className="matrix-wrap">
                  <table
                    className="confusion-matrix"
                    aria-label={`${split} confusion matrix`}
                  >
                    <thead>
                      <tr>
                        <th />
                        <th>Predicted BENIGN</th>
                        <th>Predicted ATTACK</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th>
                          Actual
                          <br />
                          <b>BENIGN</b>
                        </th>
                        <td className="correct">
                          <strong>{number(matrix[0][0])}</strong>
                          <span>True negatives</span>
                        </td>
                        <td className={matrix[0][1] ? "incorrect" : "zero"}>
                          <strong>{number(matrix[0][1])}</strong>
                          <span>False positives</span>
                        </td>
                      </tr>
                      <tr>
                        <th>
                          Actual
                          <br />
                          <b>ATTACK</b>
                        </th>
                        <td className={matrix[1][0] ? "incorrect" : "zero"}>
                          <strong>{number(matrix[1][0])}</strong>
                          <span>False negatives</span>
                        </td>
                        <td className="correct">
                          <strong>{number(matrix[1][1])}</strong>
                          <span>True positives</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No matrix in the saved report" />
              )}
              <div className="panel-note">
                Accuracy alone can hide missed attacks. Review attack recall and
                benign false positives together.
              </div>
            </Panel>
            <Panel
              title="Evaluation details"
              description="From the exported model artifacts"
            >
              <dl className="detail-list">
                <div>
                  <dt>ROC-AUC</dt>
                  <dd className="mono">
                    {metrics?.roc_auc?.toFixed(6) || "—"}
                  </dd>
                </div>
                <div>
                  <dt>False positive rate</dt>
                  <dd className="mono">
                    {percent(metrics?.false_positive_rate, 3)}
                  </dd>
                </div>
                <div>
                  <dt>Input / selected features</dt>
                  <dd className="mono">
                    {model.input_feature_count} / {model.selected_feature_count}
                  </dd>
                </div>
                <div>
                  <dt>Classifier size</dt>
                  <dd className="mono">
                    {bytes(model.evaluation?.validation?.model_bytes)}
                  </dd>
                </div>
                <div>
                  <dt>Training records</dt>
                  <dd className="mono">
                    {number(model.evaluation?.validation?.training_rows)}
                  </dd>
                </div>
                <div>
                  <dt>Training attack label</dt>
                  <dd>{model.training_attack_labels?.join(", ")}</dd>
                </div>
              </dl>
              <div className="limitation-note">
                <Database size={16} />
                <p>
                  Random holdout within one capture. These results do not
                  establish performance on new networks, days or other attack
                  types.
                </p>
              </div>
            </Panel>
          </div>
          <Panel
            title="Candidate comparison"
            description="Historical validation results used before opening the final test split"
            className="table-panel"
            action={
              <Badge tone="violet">
                <Trophy size={12} />
                Validation selection
              </Badge>
            }
          >
            {comparison?.candidates?.length ? (
              <div className="table-scroll">
                <table className="data-table comparison-table">
                  <thead>
                    <tr>
                      <th>Candidate</th>
                      <th>Accuracy</th>
                      <th>Attack recall</th>
                      <th>Attack F1</th>
                      <th>False positives</th>
                      <th>Size</th>
                      <th>Quality gate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.candidates.map((row) => (
                      <tr key={row.candidate}>
                        <td>
                          <span className="candidate-name">
                            {row.candidate === "xgboost"
                              ? "XGBoost"
                              : "Random Forest"}
                            {row.candidate ===
                              comparison.recommended_candidate && (
                              <Badge tone="green">Selected</Badge>
                            )}
                          </span>
                        </td>
                        <td className="mono">{percent(row.accuracy, 3)}</td>
                        <td className="mono">
                          {percent(row.attack_recall, 3)}
                        </td>
                        <td className="mono">{percent(row.attack_f1, 3)}</td>
                        <td className="mono">
                          {percent(row.false_positive_rate, 3)}
                        </td>
                        <td className="mono">{bytes(row.model_bytes)}</td>
                        <td>
                          <Badge
                            tone={row.passes_quality_gate ? "green" : "red"}
                          >
                            {row.passes_quality_gate ? "Passed" : "Failed"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="Comparison report unavailable" />
            )}
            <div className="panel-note">
              <GitBranch size={13} />
              Selection used validation data. The final test report did not
              choose or tune the model.
            </div>
          </Panel>
          <div className="page-footnote">
            <Timer size={13} />
            All displayed performance is saved evaluation, not accuracy measured
            on unlabeled submissions.
          </div>
        </>
      )}
    </div>
  );
}
