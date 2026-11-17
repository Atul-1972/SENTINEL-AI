import { useRef, useState } from "react";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileCheck2,
  FileSpreadsheet,
  Info,
  LoaderCircle,
  Play,
  Square,
  Trash2,
  UploadCloud,
} from "lucide-react";
import {
  Badge,
  EmptyState,
  PageHeader,
  Panel,
  PredictionTable,
  TableFooter,
} from "../components/ui";
import { download, number } from "../lib/format";
import { resultCsv } from "../services/csv";

export default function Detection({ analysis: a, dashboard: d, onInspect }) {
  const input = useRef();
  const [dragging, setDragging] = useState(false);
  const [filter, setFilter] = useState("ALL");
  const [page, setPage] = useState(0);
  const ready = d.health?.model_ready && !!d.model;
  const filtered = a.results.filter(
    (row) =>
      filter === "ALL" ||
      (filter === "ANOMALY"
        ? row.anomaly_flag
        : row.predicted_class === filter),
  );
  const maxPage = Math.max(0, Math.ceil(filtered.length / 20) - 1);
  const activePage = Math.min(page, maxPage);
  const visible = filtered.slice(activePage * 20, activePage * 20 + 20);
  const pickFile = (file) => {
    if (ready && !a.busy && !a.parsing) a.loadFile(file);
  };
  return (
    <div className="page-enter">
      <PageHeader
        eyebrow="FLOW CLASSIFICATION"
        title="Intrusion detection"
        description="Turn a traffic CSV into clear, traceable findings."
      >
        <a
          className="button secondary"
          href="/demo-flows.csv"
          download="sentinel-historical-demo.csv"
        >
          <Download size={15} />
          Download example
        </a>
      </PageHeader>
      <div className="detection-grid">
        <Panel
          title="Analyze a traffic file"
          description="CSV input · up to 20,000 flows per file"
        >
          <div
            className={`drop-zone ${dragging ? "dragging" : ""} ${!ready ? "unavailable" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              if (ready) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              pickFile(event.dataTransfer.files[0]);
            }}
          >
            <div className="upload-icon">
              <UploadCloud size={29} strokeWidth={1.5} />
            </div>
            <h3>Drop your network traffic CSV</h3>
            <p>or choose a file from your computer</p>
            <input
              ref={input}
              id="traffic-file"
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              aria-label="Upload traffic CSV"
              disabled={!ready || a.busy || a.parsing}
              onChange={(event) => {
                pickFile(event.target.files[0]);
                event.target.value = "";
              }}
            />
            <button
              className="button secondary"
              onClick={() => input.current.click()}
              disabled={!ready || a.busy || a.parsing}
            >
              <FileSpreadsheet size={15} />
              Choose CSV
            </button>
            <small>
              {ready
                ? "Maximum 25 MB · numeric flow features"
                : "Connect to the API to load the feature schema"}
            </small>
          </div>
          <div className="example-row">
            <span>Just exploring?</span>
            <button
              className="text-button"
              disabled={!ready || a.busy || a.parsing}
              onClick={a.loadExample}
            >
              Load historical example
              <ChevronRight size={14} />
            </button>
          </div>
          {a.parsing && (
            <div className="inline-status" role="status">
              <LoaderCircle size={15} className="spin" />
              Reading and validating your CSV…
            </div>
          )}
          {a.dataset && (
            <div className="file-summary">
              <div className="file-summary-icon">
                <FileCheck2 size={22} />
              </div>
              <div>
                <strong title={a.dataset.name}>{a.dataset.name}</strong>
                <small>
                  {number(a.dataset.records.length)} flows ·{" "}
                  {d.model?.input_feature_count} features validated
                </small>
              </div>
              <button
                className="icon-button"
                aria-label="Clear uploaded file"
                disabled={a.busy}
                onClick={a.clear}
              >
                <Trash2 size={15} />
              </button>
            </div>
          )}
          {a.dataset && (
            <details className="preparation-notes">
              <summary>CSV preparation notes</summary>
              <p>
                {number(a.dataset.convertedMissing)} missing or non-finite cells
                mapped to null for the saved imputer.
              </p>
              <p>
                {a.dataset.renamed.length} duplicate headers renamed;{" "}
                {a.dataset.ignoredColumns.length} extra columns excluded. Label
                values are kept only for result reference.
              </p>
            </details>
          )}
          <div className="analysis-actions">
            <label className="field-label">
              Submission source
              <select
                value={a.source}
                onChange={(event) => a.setSource(event.target.value)}
                disabled={a.busy || a.progress > 0}
              >
                <option value="historical">Historical dataset</option>
                <option value="simulated">Simulated dataset</option>
                <option value="user_provided">User-provided records</option>
              </select>
            </label>
            <button
              className={`button ${a.finished ? "completed" : "primary"}`}
              disabled={
                !ready || !a.dataset || a.busy || a.parsing || a.finished
              }
              onClick={a.analyze}
            >
              {a.busy ? (
                <LoaderCircle className="spin" size={16} />
              ) : a.finished ? (
                <CheckCircle2 size={16} />
              ) : (
                <Play size={15} />
              )}
              {a.busy
                ? "Analyzing…"
                : a.finished
                  ? "Analysis complete"
                  : a.progress
                    ? "Resume analysis"
                    : "Analyze flows"}
            </button>
          </div>
          {(a.busy || a.progress > 0) && (
            <div className="analysis-progress" aria-live="polite">
              <div>
                <span>
                  {number(a.progress)} / {number(a.dataset?.records.length)}{" "}
                  flows completed
                </span>
                {a.busy && (
                  <button
                    className="text-button"
                    disabled={a.stopping}
                    onClick={a.stop}
                  >
                    <Square size={12} />
                    {a.stopping ? "Stopping…" : "Stop after batch"}
                  </button>
                )}
              </div>
              <progress
                value={a.progress}
                max={a.dataset?.records.length || 1}
              />
            </div>
          )}
          {a.error && (
            <div className="inline-error" role="alert">
              <Info size={16} />
              <span>{a.error}</span>
            </div>
          )}
        </Panel>
        <Panel
          title="From flow to finding"
          description="The same pipeline used in training"
          className="analysis-guide"
        >
          <div className="guide-step">
            <span>01</span>
            <div>
              <h3>Validate the features</h3>
              <p>
                Match the model's {d.model?.input_feature_count || 78} input
                columns. Missing values use saved training medians.
              </p>
            </div>
          </div>
          <div className="guide-step">
            <span>02</span>
            <div>
              <h3>Classify & inspect</h3>
              <p>
                The classifier returns BENIGN or ATTACK. Isolation Forest adds a
                separate anomaly flag.
              </p>
            </div>
          </div>
          <div className="guide-step">
            <span>03</span>
            <div>
              <h3>Prioritize your review</h3>
              <p>
                Risk rules create alerts. Each prediction is saved with its
                source and model version.
              </p>
            </div>
          </div>
          <div className="guide-note">
            <Info size={16} />
            <p>
              Training coverage is BENIGN and DDoS. Model probabilities are
              uncalibrated; anomaly scores are not probabilities.
            </p>
          </div>
        </Panel>
      </div>
      <Panel
        title="Analysis results"
        description={
          a.results.length
            ? `${number(a.results.length)} actual predictions returned by the API`
            : "Results appear after you run an analysis"
        }
        action={
          <button
            className="button secondary small"
            disabled={!a.results.length}
            onClick={() =>
              download(
                resultCsv(a.results),
                "sentinel-predictions.csv",
                "text/csv;charset=utf-8",
              )
            }
          >
            <Download size={14} />
            Export results
          </button>
        }
        className="table-panel"
      >
        {a.results.length ? (
          <>
            <div className="table-toolbar">
              <div className="segmented">
                {[
                  ["ALL", "All flows"],
                  ["BENIGN", "Benign"],
                  ["ATTACK", "Attack"],
                  ["ANOMALY", "Anomalies"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    className={filter === value ? "selected" : ""}
                    aria-pressed={filter === value}
                    onClick={() => {
                      setFilter(value);
                      setPage(0);
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <Badge>{number(filtered.length)} matching</Badge>
            </div>
            <PredictionTable rows={visible} onSelect={onInspect} showInputRow />
            <TableFooter showing={visible.length} total={filtered.length}>
              <div className="pagination">
                <button
                  className="icon-button"
                  aria-label="Previous result page"
                  disabled={!activePage}
                  onClick={() => setPage(activePage - 1)}
                >
                  <ChevronLeft size={16} />
                </button>
                <span>
                  {activePage + 1} / {maxPage + 1}
                </span>
                <button
                  className="icon-button"
                  aria-label="Next result page"
                  disabled={activePage >= maxPage}
                  onClick={() => setPage(activePage + 1)}
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </TableFooter>
          </>
        ) : (
          <EmptyState
            icon={FileSpreadsheet}
            title="Ready when you are"
            description="Upload your traffic file or load the historical example, then select Analyze flows."
          />
        )}
      </Panel>
    </div>
  );
}
