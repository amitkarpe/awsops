import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Refine, useOne, type DataProvider } from "@refinedev/core";
import { Button, ThemeToggle } from "./ui";
import { Icon, categoryIcon } from "./icons";
import "./style.css";

type Rule = {
  accountAlias: string;
  ConfigRuleName: string;
  category: string;
  status: string;
  count: number | null;
  capped: boolean;
  warning: boolean;
};
type AccountStatus = {
  alias: string;
  available: boolean;
  fetchedAt: string | null;
  ruleCount: number | null;
  message?: string;
};
type Snapshot = {
  environment: string;
  region: string;
  rules: Rule[];
  recorders: Record<string, unknown>[];
  fetchedAt: string | null;
  available: boolean;
  partial: boolean;
  availableAccounts: number;
  totalAccounts: number;
  accounts: AccountStatus[];
};

const LAB_ACCOUNTS = ["lab-dev", "lab-poc", "lab-qa", "lab-sec"];
const CATEGORIES = ["S3", "Security Groups"];

async function jsonBody(response: Response, fallback: string) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json"))
    throw Error(`HTTP ${response.status || "?"}: ${response.statusText || fallback}`);
  const body = await response.json();
  if (!response.ok) throw Error(body?.error || `HTTP ${response.status}: ${fallback}`);
  return body;
}
async function request(url: string) {
  return jsonBody(await fetch(url, { cache: "no-store" }), "Read failed");
}
const blocked = async (): Promise<never> => {
  throw Error("Read-only data provider");
};
const dataProvider: DataProvider = {
  getApiUrl: () => "/api",
  getList: blocked,
  create: blocked,
  update: blocked,
  deleteOne: blocked,
  getOne: async ({ id, meta }) => ({
    data: await request(
      `/api/controls?environment=${encodeURIComponent(String(id))}&refresh=${meta?.refresh ? 1 : 0}`,
    ),
  }),
};
const date = (value?: string | null) =>
  value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : "Not reported";

function Status({ value }: { value: string }) {
  const kind =
    value === "COMPLIANT" ? "good" : value === "NON_COMPLIANT" ? "danger" : "warning";
  return (
    <span className={`status-chip ${kind}`}>
      <Icon name={kind === "good" ? "check" : kind === "danger" ? "alert" : "clock"} size={14} />
      {value.replaceAll("_", " ")}
    </span>
  );
}

function App() {
  const [environment, setEnvironment] = useState("ALL");
  const [category, setCategory] = useState("All Controls");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const [refresh, setRefresh] = useState(0);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [section, setSection] = useState<"dashboard" | "controls" | "accounts">("dashboard");
  const [mode, setMode] = useState("Checking mode");
  const [dashboard, setDashboard] = useState<"management" | "security" | "operations">(() => {
    try {
      const saved = localStorage.getItem("awsops-config2-dashboard");
      if (saved === "management" || saved === "security" || saved === "operations") return saved;
    } catch {
      // Browser storage is optional.
    }
    return "management";
  });

  const { query } = useOne<Snapshot>({
    resource: "controls",
    id: environment,
    meta: { refresh },
    queryOptions: {
      enabled: Boolean(environment),
      retry: false,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      staleTime: Infinity,
    },
  });

  const snapshot =
    !query.isError && query.data?.data.environment === environment ? query.data.data : undefined;
  const hasEvidence = Boolean(snapshot && snapshot.available === true);

  useEffect(() => {
    let cancelled = false;
    request("/api/health")
      .then((health) => {
        if (
          health.mode !== "AWS_READ_ONLY" ||
          health.region !== "ap-southeast-1" ||
          health.allAccounts !== true ||
          health.remediation !== false ||
          !Array.isArray(health.environments) ||
          health.environments.length !== LAB_ACCOUNTS.length ||
          !LAB_ACCOUNTS.every(
            (alias) => health.environments.filter((item: string) => item === alias).length === 1,
          )
        )
          throw Error("Unsupported config2 runtime");
        if (!cancelled) setMode("AWS_READ_ONLY");
      })
      .catch(() => {
        if (!cancelled) setMode("Unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const chooseDashboard = (value: "management" | "security" | "operations") => {
    setDashboard(value);
    setSection("dashboard");
    try {
      localStorage.setItem("awsops-config2-dashboard", value);
    } catch {
      // Browser storage is optional.
    }
  };

  const rules = hasEvidence ? snapshot?.rules || [] : [];
  const filtered = rules
    .filter(
      (rule) =>
        (category === "All Controls" || rule.category === category) &&
        (status === "ALL" ||
          (status === "ATTENTION"
            ? ["INSUFFICIENT_DATA", "NOT_APPLICABLE"].includes(rule.status) || rule.warning
            : rule.status === status)) &&
        `${rule.accountAlias} ${rule.ConfigRuleName} ${rule.category}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort(
      (a, b) =>
        a.accountAlias.localeCompare(b.accountAlias) ||
        a.ConfigRuleName.localeCompare(b.ConfigRuleName),
    );

  const compliant = rules.filter((rule) => rule.status === "COMPLIANT").length;
  const noncompliant = rules.filter((rule) => rule.status === "NON_COMPLIANT").length;
  const attention = rules.filter(
    (rule) => ["INSUFFICIENT_DATA", "NOT_APPLICABLE"].includes(rule.status) || rule.warning,
  ).length;
  const evaluated = compliant + noncompliant;
  const compliancePct = evaluated ? Math.round((compliant / evaluated) * 100) : 0;
  const affectedResources = rules
    .filter((rule) => rule.status === "NON_COMPLIANT")
    .reduce((sum, rule) => sum + (rule.count ?? 0), 0);
  const accountsAtRisk = new Set(
    rules.filter((rule) => rule.status === "NON_COMPLIANT").map((rule) => rule.accountAlias),
  ).size;

  const accountGroups = LAB_ACCOUNTS.map((alias) => {
    const group = rules.filter((rule) => rule.accountAlias === alias);
    const account = snapshot?.accounts?.find((item) => item.alias === alias);
    return {
      alias,
      available: account?.available === true,
      total: group.length,
      compliant: group.filter((rule) => rule.status === "COMPLIANT").length,
      noncompliant: group.filter((rule) => rule.status === "NON_COMPLIANT").length,
    };
  });
  const controlGroups = [
    "s3-bucket-level-public-access-prohibited",
    "restricted-ssh",
  ].map((name) => {
    const group = rules.filter((rule) => rule.ConfigRuleName === name);
    return {
      name,
      total: group.length,
      noncompliant: group.filter((rule) => rule.status === "NON_COMPLIANT").length,
      affected: group
        .filter((rule) => rule.status === "NON_COMPLIANT")
        .reduce((sum, rule) => sum + (rule.count ?? 0), 0),
    };
  });
  const metrics = [
    { label: "Account / control checks", count: rules.length, icon: "grid", tone: "neutral" },
    { label: "Compliance", count: `${compliancePct}%`, icon: "check", tone: "good" },
    { label: "Non-compliant checks", count: noncompliant, icon: "alert", tone: "danger" },
    { label: "Affected resources", count: affectedResources, icon: "layers", tone: "warning" },
  ];

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Icon name="shield" size={25} /></span>
          <div><strong>SecCop</strong><small>CONFIG EXPLORER</small></div>
          <button
            type="button"
            className="nav-toggle"
            aria-label="Toggle navigation"
            aria-expanded={navigationOpen}
            onClick={() => setNavigationOpen((value) => !value)}
          ><Icon name={navigationOpen ? "close" : "menu"} /></button>
        </div>
        <div className={`sidebar-content ${navigationOpen ? "is-open" : ""}`}>
          <div className="sidebar-label">Workspace</div>
          <nav aria-label="Primary navigation">
            <button className="category-button" aria-pressed={section === "dashboard"} onClick={() => setSection("dashboard")}><Icon name="dashboard" /><span>Dashboard</span></button>
            <button className="category-button" aria-pressed={section === "controls"} onClick={() => setSection("controls")}><Icon name="shield" /><span>Controls</span><span className="category-count">{hasEvidence ? rules.length : "--"}</span></button>
            <button className="category-button" aria-pressed={section === "accounts"} onClick={() => setSection("accounts")}><Icon name="layers" /><span>Accounts</span><span className="category-count">4</span></button>
          </nav>
          <div className="sidebar-label secondary-label">Control library</div>
          <nav aria-label="Control categories">
            {["All Controls", ...CATEGORIES].map((item) => {
              const group = rules.filter((rule) => item === "All Controls" || rule.category === item);
              return (
                <button
                  key={item}
                  className="category-button"
                  aria-pressed={section === "controls" && category === item}
                  onClick={() => { setCategory(item); setSection("controls"); }}
                >
                  <Icon name={categoryIcon[item]} />
                  <span>{item}</span>
                  <span className="category-count">
                    {hasEvidence ? `${group.length} / ${group.filter((rule) => rule.status === "NON_COMPLIANT").length}` : "--"}
                  </span>
                </button>
              );
            })}
          </nav>
          <p className="sidebar-hint">Counts: total / non-compliant</p>
          <div className="sidebar-footer"><Icon name="shield" /><div>Read-only exploration<small>No remediation actions</small></div></div>
        </div>
      </aside>

      <main id="main-content" className="main-content" tabIndex={-1}>
        <header className="page-header">
          <div>
            <div className="eyebrow">AWS Config · Multi-account security</div>
            <h1>{section === "dashboard" ? "Compliance dashboard" : section === "accounts" ? "Account fleet" : "Config controls"}</h1>
            <p className="muted page-intro">
              {section === "dashboard"
                ? "Current read-only compliance posture across the four registered LAB aliases."
                : section === "accounts"
                  ? "Per-account availability and compliance posture."
                  : "Exactly two approved AWS Config controls per registered LAB alias."}
            </p>
          </div>
          <div className="header-actions">
            <ThemeToggle />
            <Button asChild variant="outline">
              <a href="https://sec2.astromedicomp.org/"><Icon name="shield" />Compliance Agent</a>
            </Button>
            <label className="selector-label">Account
              <select value={environment} onChange={(event) => setEnvironment(event.target.value)}>
                <option value="ALL">All Accounts</option>
                {LAB_ACCOUNTS.map((alias) => <option key={alias} value={alias}>{alias}</option>)}
              </select>
            </label>
            <Button disabled={query.isFetching} onClick={() => setRefresh((value) => value + 1)}>
              <Icon name="refresh" className={query.isFetching ? "spinning" : ""} />Refresh
            </Button>
          </div>
        </header>

        <div className="evidence-bar">
          <span className="mode-label"><Icon name="shield" size={15} />{mode}</span>
          <span className="muted">Read-only AWS Config evidence</span>
          <span className="fetch-time"><Icon name="clock" size={14} />Oldest included fetch: {date(snapshot?.fetchedAt)}</span>
        </div>

        {mode === "Unavailable" && <p role="alert" className="notice danger">Config2 runtime unavailable. No compliance result is asserted.</p>}
        {snapshot?.partial && <p role="alert" className="notice warning"><Icon name="alert" />Partial evidence: {snapshot.availableAccounts} of {snapshot.totalAccounts} requested accounts are complete. Missing accounts are not treated as compliant.</p>}
        {query.isError && <p role="alert" className="notice danger"><Icon name="alert" />{query.error?.message}. No successful inventory is asserted.</p>}
        {query.isFetching && <p role="status" className="loading-note"><Icon name="refresh" className="spinning" />Reading current Config evidence...</p>}

        {section === "dashboard" && <>
          <section className="dashboard-switcher" aria-label="Dashboard view">
            <div><strong>Dashboard view</strong><span className="muted">Presentation only; all views use the same evidence</span></div>
            <div className="dashboard-tabs">
              {(["management", "security", "operations"] as const).map((item) => (
                <Button key={item} variant={dashboard === item ? "default" : "outline"} onClick={() => chooseDashboard(item)}>
                  <Icon name={item === "management" ? "chart" : item === "security" ? "shield" : "server"} />
                  {item[0].toUpperCase() + item.slice(1)}
                </Button>
              ))}
            </div>
          </section>

          <section aria-label="Summary" className="summary-grid">
            {metrics.map(({ label, count, icon, tone }) => (
              <div key={label} className={`summary-card ${tone}`}>
                <div className="summary-top"><span>{label}</span><span className="metric-symbol"><Icon name={icon} size={20} /></span></div>
                <strong className="summary-count">{hasEvidence ? count : "--"}</strong>
                <small>{snapshot?.partial ? "Available complete accounts only" : "Current Config snapshot"}</small>
              </div>
            ))}
          </section>

          {dashboard === "management" && <section className="dashboard-grid">
            <article className="insight-card hero-card">
              <div className="card-heading"><div><span className="eyebrow">Overall posture</span><h2>Compliance coverage</h2></div><span className="status-chip good">{compliancePct}% compliant</span></div>
              <div className="compliance-visual">
                <div className="donut" style={{ "--pct": compliancePct } as React.CSSProperties}><div><strong>{compliancePct}%</strong><span>compliant</span></div></div>
                <div className="legend">
                  <span><i className="dot good-dot" />Compliant <b>{compliant}</b></span>
                  <span><i className="dot danger-dot" />Non-compliant <b>{noncompliant}</b></span>
                  <span><i className="dot warning-dot" />Attention <b>{attention}</b></span>
                </div>
              </div>
            </article>
            <article className="insight-card">
              <div className="card-heading"><div><span className="eyebrow">Risk concentration</span><h2>Controls needing attention</h2></div><span className="big-number">{controlGroups.filter((item) => item.noncompliant).length}</span></div>
              <div className="rank-list">{controlGroups.map((item) => <button key={item.name} className="rank-row" onClick={() => { setSearch(item.name); setSection("controls"); }}>
                <span><b>{item.name}</b><small>{item.noncompliant} of {item.total} checks non-compliant</small></span>
                <span className="risk-count">{item.affected} resources</span>
              </button>)}</div>
            </article>
            <article className="insight-card wide-card">
              <div className="card-heading"><div><span className="eyebrow">Fleet</span><h2>Accounts needing attention</h2></div><span className="big-number">{accountsAtRisk}/4</span></div>
              <div className="fleet-strip">{accountGroups.map((account) => <button key={account.alias} className="fleet-pill" onClick={() => { setEnvironment(account.alias); setSection("controls"); }}>
                <span className={`fleet-state ${!account.available ? "warning" : account.noncompliant ? "danger" : "good"}`} />
                <b>{account.alias}</b><small>{!account.available ? "Unavailable" : account.noncompliant ? `${account.noncompliant} issue${account.noncompliant === 1 ? "" : "s"}` : "Compliant"}</small>
              </button>)}</div>
            </article>
          </section>}

          {dashboard === "security" && <section className="dashboard-grid">
            <article className="insight-card wide-card">
              <div className="card-heading"><div><span className="eyebrow">Security view</span><h2>Control risk by account coverage</h2></div><span className="status-chip danger">{noncompliant} open checks</span></div>
              <div className="control-bars">{controlGroups.map((item) => <button key={item.name} className="control-bar" onClick={() => { setSearch(item.name); setSection("controls"); }}>
                <span className="bar-label"><b>{item.name}</b><small>{item.affected} affected resources</small></span>
                <span className="bar-track"><i style={{ width: (item.total ? Math.round(item.noncompliant / item.total * 100) : 0) + "%" }} /></span>
                <span className="bar-value">{item.noncompliant}/{item.total}</span>
              </button>)}</div>
            </article>
          </section>}

          {dashboard === "operations" && <section className="dashboard-grid">
            <article className="insight-card wide-card">
              <div className="card-heading"><div><span className="eyebrow">Operations view</span><h2>Account fleet health</h2></div><span className="status-chip good">{snapshot?.availableAccounts ?? 0}/{snapshot?.totalAccounts ?? 4} complete</span></div>
              <div className="account-table">{accountGroups.map((account) => <button key={account.alias} className="account-row" onClick={() => { setEnvironment(account.alias); setSection("controls"); }}>
                <span><b>{account.alias}</b><small>{account.total} checks</small></span>
                <span>{account.compliant} compliant</span>
                <span className={account.noncompliant ? "danger-text" : "good-text"}>{account.noncompliant} non-compliant</span>
                <Icon name="chevron" size={14} />
              </button>)}</div>
            </article>
            <article className="insight-card">
              <div className="card-heading"><div><span className="eyebrow">Evidence</span><h2>Inventory freshness</h2></div><Icon name="clock" size={22} /></div>
              <strong className="freshness-value">{date(snapshot?.fetchedAt)}</strong>
              <p className="muted">Oldest included successful fetch for the current scope.</p>
            </article>
          </section>}
        </>}

        {section === "accounts" && <section className="account-fleet-panel">
          <div className="card-heading"><div><span className="eyebrow">Account fleet</span><h2>4 registered LAB aliases</h2></div><span className="muted">Exact bounded demo scope</span></div>
          <div className="fleet-grid">{accountGroups.map((account) => <button key={account.alias} className="fleet-card" onClick={() => { setEnvironment(account.alias); setSection("controls"); }}>
            <span className="account-symbol"><Icon name="layers" size={19} /></span>
            <span><b>{account.alias}</b><small>{account.available ? "Complete read available" : "Unavailable / incomplete"}</small></span>
            <span className="fleet-metrics"><b>{account.compliant}</b> compliant · <b className={account.noncompliant ? "danger-text" : ""}>{account.noncompliant}</b> non-compliant</span>
            <Icon name="chevron" size={15} />
          </button>)}</div>
        </section>}

        <section className={`table-panel ${section === "controls" ? "" : "section-secondary"}`} aria-label="Control inventory">
          <div className="table-heading"><h2>{category}</h2><span className="muted">{hasEvidence ? filtered.length : "--"} shown</span></div>
          <div className="quick-filters" aria-label="Quick views">
            <span className="muted">Quick view</span>
            <button aria-pressed={status === "ALL"} onClick={() => setStatus("ALL")}>All <b>{rules.length}</b></button>
            <button aria-pressed={status === "NON_COMPLIANT"} onClick={() => setStatus("NON_COMPLIANT")}>Non-compliant <b>{noncompliant}</b></button>
            <button aria-pressed={status === "ATTENTION"} onClick={() => setStatus("ATTENTION")}>Attention <b>{attention}</b></button>
          </div>
          <div className="table-toolbar">
            <label className="search-field"><Icon name="search" /><input aria-label="Search controls" placeholder="Search account or control" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
            <label className="filter-field"><Icon name="filter" /><select aria-label="Compliance filter" value={status} onChange={(event) => setStatus(event.target.value)}>
              {["ALL", "NON_COMPLIANT", "ATTENTION", "COMPLIANT", "INSUFFICIENT_DATA", "NOT_APPLICABLE"].map((item) => <option key={item} value={item}>{item === "ALL" ? "All statuses" : item === "ATTENTION" ? "Attention" : item.replaceAll("_", " ")}</option>)}
            </select></label>
          </div>
          <div className="table-scroll" role="region" aria-label="Scrollable controls table" tabIndex={0}>
            <table>
              <thead><tr><th>Status</th><th>Account</th><th>Control</th><th>Category</th><th>Non-compliant</th></tr></thead>
              <tbody>{filtered.map((rule) => <tr key={`${rule.accountAlias}:${rule.ConfigRuleName}`}>
                <td><Status value={rule.status} /></td>
                <td><span className="account-tag">{rule.accountAlias}</span></td>
                <td>{rule.ConfigRuleName}</td>
                <td><span className="category-cell"><Icon name={categoryIcon[rule.category]} size={15} />{rule.category}</span></td>
                <td className="numeric">{rule.count == null ? "--" : `${rule.count}${rule.capped ? "+" : ""}`}</td>
              </tr>)}</tbody>
            </table>
            {!filtered.length && !query.isFetching && <p className="empty-state"><Icon name="search" size={28} />{!hasEvidence ? "Inventory unavailable" : "No matching controls"}</p>}
          </div>
          <footer className="table-footer">{hasEvidence ? `${filtered.length} of ${rules.length}` : "No current"} account/control checks. Partial or unavailable accounts are never counted as compliant.</footer>
        </section>

        <p className="page-footer"><Icon name="shield" size={14} />Read-only Config evidence. No remediation, re-arm, preview, confirmation, or generic AWS action exists in config2.</p>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <Refine dataProvider={dataProvider} options={{ disableTelemetry: true }}>
    <App />
  </Refine>,
);
