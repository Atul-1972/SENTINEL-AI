import { lazy, Suspense, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  BookOpen,
  ChartColumn,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Download,
  Info,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Radar,
  RefreshCw,
  ScanLine,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
  X,
} from "lucide-react";
import { Badge } from "./components/ui";
import FlowInspector, { Modal } from "./components/FlowInspector";
import { useDashboard } from "./hooks/useDashboard";
import { useAnalysis } from "./hooks/useAnalysis";
import { download, shortTime } from "./lib/format";
import { API_TARGET } from "./services/api";

const Overview = lazy(() => import("./pages/Overview"));
const Detection = lazy(() => import("./pages/Detection"));
const Threats = lazy(() => import("./pages/Threats"));
const Performance = lazy(() => import("./pages/Performance"));
const Monitoring = lazy(() => import("./pages/Monitoring"));

const pages = [
  {
    id: "overview",
    title: "Security overview",
    short: "Overview",
    icon: LayoutDashboard,
  },
  {
    id: "detection",
    title: "Intrusion detection",
    short: "Intrusion detection",
    icon: ScanLine,
  },
  {
    id: "threats",
    title: "Threat analysis",
    short: "Threat analysis",
    icon: Radar,
  },
  {
    id: "performance",
    title: "Model performance",
    short: "Model performance",
    icon: ChartColumn,
  },
  {
    id: "monitoring",
    title: "MLOps monitoring",
    short: "MLOps monitoring",
    icon: Workflow,
  },
];
const readPage = () =>
  pages.some((page) => page.id === window.location.hash.slice(1))
    ? window.location.hash.slice(1)
    : "overview";

export default function App() {
  const [page, setPage] = useState(readPage);
  const [mobileNav, setMobileNav] = useState(false);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState(null);
  const [toast, setToast] = useState("");
  const dashboard = useDashboard();
  const analysis = useAnalysis(
    dashboard.model?.feature_names,
    dashboard.refresh,
  );
  const current = pages.find((item) => item.id === page);
  const connected = dashboard.health?.status === "ok" && !dashboard.error;
  const status =
    dashboard.loading && !dashboard.updatedAt
      ? "Connecting"
      : connected
        ? "Connected"
        : dashboard.health
          ? "Needs attention"
          : "Disconnected";

  useEffect(() => {
    const change = () => {
      setPage(readPage());
      setMobileNav(false);
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    document.title = `${current.title} · SENTINEL AI`;
  }, [current.title]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!mobileNav) return;
    const close = (event) => {
      if (event.key === "Escape") setMobileNav(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [mobileNav]);

  const navigate = (id) => {
    window.location.hash = id;
    setMobileNav(false);
  };
  function exportSnapshot() {
    download(
      JSON.stringify(
        {
          captured_at: new Date().toISOString(),
          last_successful_refresh: dashboard.updatedAt,
          connection_status: status,
          stats: dashboard.stats,
          model_version: dashboard.model?.model_version,
          evaluation: dashboard.model?.evaluation,
          alerts: dashboard.alerts,
        },
        null,
        2,
      ),
      "sentinel-workspace-snapshot.json",
    );
    setToast("Workspace snapshot exported.");
  }
  const props = { dashboard, analysis, navigate, onInspect: setSelectedFlow };
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content").focus();
        }}
      >
        Skip to content
      </a>
      {mobileNav && (
        <button
          className="mobile-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileNav(false)}
        />
      )}
      <aside className={`sidebar ${mobileNav ? "is-open" : ""}`}>
        <button
          className="brand"
          onClick={() => navigate("overview")}
          aria-label="SENTINEL AI overview"
        >
          <span className="brand-mark">
            <ShieldCheck size={25} strokeWidth={1.7} />
          </span>
          <span className="brand-word">
            SENTINEL<span>AI</span>
            <small>SECURITY WORKSPACE</small>
          </span>
        </button>
        <div className="workspace-label">
          <span className="workspace-symbol">
            <Activity size={15} />
          </span>
          <div>
            <strong>Local workspace</strong>
            <small>Academic prototype</small>
          </div>
          <ChevronDown size={13} />
        </div>
        <div className="nav-section-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              title={item.title}
              aria-current={page === item.id ? "page" : undefined}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => setMobileNav(false)}
            >
              <item.icon size={18} strokeWidth={1.7} />
              <span>{item.short}</span>
              {page === item.id && <i />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-engine">
            <span className={`mini-dot ${connected ? "green" : "amber"}`} />
            <div>
              <strong>
                {dashboard.model
                  ? dashboard.model.active_model === "xgboost"
                    ? "XGBoost engine"
                    : "Random Forest engine"
                  : "Detection engine"}
              </strong>
              <small>
                {connected
                  ? "Model ready for inference"
                  : "Waiting for connection"}
              </small>
            </div>
          </div>
          <a
            className="sidebar-link"
            href={`${API_TARGET}/docs`}
            target="_blank"
            rel="noreferrer"
          >
            <BookOpen size={16} />
            <span>API documentation</span>
            <ArrowUpRight size={14} />
          </a>
          <div className="sidebar-caption">
            Built for learning.
            <br />
            Grounded in real predictions.
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMobileNav(true)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>{current.title}</strong>
          </div>
          <div className="topbar-actions">
            <span className="sync-time">
              <Clock3 size={12} />
              {dashboard.updatedAt
                ? `Synced ${shortTime(dashboard.updatedAt)}`
                : "Awaiting first sync"}
            </span>
            <button
              className={`connection-pill ${connected ? "online" : ""}`}
              onClick={() => setConnectionOpen(true)}
            >
              <i className="status-dot" />
              API {status}
              <ChevronDown size={12} />
            </button>
            <div className="topbar-divider" />
            <button
              className="icon-button"
              aria-label="Export workspace snapshot"
              title="Export workspace snapshot"
              onClick={exportSnapshot}
              disabled={!dashboard.stats}
            >
              <Download size={17} />
            </button>
            <button
              className="icon-button notification-button"
              aria-label="View security alerts"
              title="View security alerts"
              onClick={() => navigate("threats")}
            >
              <Bell size={18} />
              {!!dashboard.stats?.high_risk_alerts && <i />}
            </button>
            <button
              className="icon-button"
              aria-label="Connection settings"
              title="Connection settings"
              onClick={() => setConnectionOpen(true)}
            >
              <SlidersHorizontal size={17} />
            </button>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {dashboard.error && (
            <div className="connection-banner" role="alert">
              <Info size={18} />
              <div>
                <strong>
                  {dashboard.updatedAt
                    ? "Some data could not refresh"
                    : "The API connection needs attention"}
                </strong>
                <p>
                  {dashboard.updatedAt
                    ? `Showing the last successful snapshot from ${shortTime(dashboard.updatedAt)}. `
                    : ""}
                  {dashboard.error.includes("fetch")
                    ? "Start the local Docker API and try again."
                    : dashboard.error}
                </p>
              </div>
              <button
                className="button secondary small"
                onClick={dashboard.refresh}
                disabled={dashboard.loading}
              >
                <RefreshCw size={13} />
                Retry
              </button>
            </div>
          )}
          <Suspense
            fallback={
              <div className="loading-state" role="status">
                <LoaderCircle className="spin" size={22} />
                Loading workspace…
              </div>
            }
          >
            {page === "overview" && <Overview {...props} />}
            {page === "detection" && <Detection {...props} />}
            {page === "threats" && <Threats {...props} />}
            {page === "performance" && <Performance {...props} />}
            {page === "monitoring" && <Monitoring {...props} />}
          </Suspense>
          <footer className="workspace-footer">
            <span>
              <ShieldCheck size={13} />
              SENTINEL AI <i />
              Educational intrusion detection
            </span>
            <span>
              {dashboard.model?.model_version || "Local inference workspace"}
            </span>
          </footer>
        </main>
      </div>
      <FlowInspector
        predictionId={selectedFlow}
        onClose={() => setSelectedFlow(null)}
      />
      <Modal
        open={connectionOpen}
        onClose={() => setConnectionOpen(false)}
        title="Connection & refresh"
        description="Your local inference workspace"
      >
        <dl className="detail-list">
          <div>
            <dt>API status</dt>
            <dd>
              <Badge tone={connected ? "green" : "amber"} dot>
                {status}
              </Badge>
            </dd>
          </div>
          <div>
            <dt>Backend target</dt>
            <dd className="mono">{API_TARGET}</dd>
          </div>
          <div>
            <dt>Database</dt>
            <dd>
              {dashboard.health?.database_ready
                ? "SQLite ready"
                : "Unavailable"}
            </dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd className="mono">
              {dashboard.model?.model_version || "Unavailable"}
            </dd>
          </div>
        </dl>
        <label className="toggle-row">
          <div>
            <strong>Automatic refresh</strong>
            <p>Refresh displayed API data every 15 seconds.</p>
          </div>
          <input
            type="checkbox"
            aria-label="Automatic refresh"
            checked={dashboard.autoRefresh}
            onChange={(event) => dashboard.setAutoRefresh(event.target.checked)}
          />
        </label>
        <div className="connection-actions">
          <button
            className="button primary"
            onClick={dashboard.refresh}
            disabled={dashboard.loading}
          >
            {dashboard.loading ? (
              <LoaderCircle className="spin" size={15} />
            ) : (
              <RefreshCw size={15} />
            )}
            Refresh now
          </button>
          <a
            className="button secondary"
            href={`${API_TARGET}/docs`}
            target="_blank"
            rel="noreferrer"
          >
            Swagger docs
            <ArrowUpRight size={15} />
          </a>
        </div>
      </Modal>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={16} />
          {toast}
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setToast("")}
          >
            <X size={13} />
          </button>
        </div>
      )}
    </div>
  );
}
