import {
  applyDocument,
  formatClock,
  formatExact,
  formatWhen,
  getLocale,
  localeChoices,
  onLocale,
  phrase,
  setLocale,
  t,
} from "./i18n.js";

const SVG = "http://www.w3.org/2000/svg";
const LINKS = {
  grafanaTaskflow: "http://127.0.0.1:41833/d/taskflow-health/taskflow-service-health",
  grafanaKubemedic: "http://127.0.0.1:41833/d/kubemedic-reliability/kubemedic-reliability-overview",
  prometheus: "http://127.0.0.1:41834",
};
const PRIMARY_EVIDENCE = [
  "Waiting reason",
  "Termination reason",
  "Exit code",
  "Restart count",
  "Image",
  "Deployment",
  "Memory limit",
  "Pod phase",
  "Node",
];
const AUDIT_FIELDS = [
  ["images", "remediation.images"],
  ["replicas", "remediation.replicas"],
  ["ready", "remediation.ready"],
  ["updated", "remediation.updated"],
  ["revision", "remediation.revision"],
  ["generation", "remediation.generation"],
  ["observed_generation", "remediation.observed"],
];
const ISSUE_TYPES = [
  "CrashLoopBackOff",
  "ImagePullBackOff",
  "ErrImagePull",
  "OOMKilled",
  "CreateContainerConfigError",
  "CreateContainerError",
  "FailedScheduling",
  "FailedMount",
  "ReadinessProbeFailed",
  "LivenessProbeFailed",
  "DatabaseConnectivity",
  "RepeatedRestarts",
  "UnavailableReplicas",
];
const ICONS = {
  overview: ["M4 4h7v7H4z", "M13 4h7v7h-7z", "M4 13h7v7H4z", "M13 13h7v7h-7z"],
  investigations: ["M7 3h8l4 4v14H7z", "M15 3v4h4"],
  remediation: ["M12 3l8 3v6c0 4.5-3.2 7.6-8 9-4.8-1.4-8-4.5-8-9V6z"],
  observability: ["M3 12h4l2-6 4 12 2-6h6"],
  system: ["M4 6h16v10H4z", "M8 20h8", "M12 16v4"],
  check: ["M5 12l5 5 9-10"],
  alert: ["M12 4l9 16H3z", "M12 10v4", "M12 17h.01"],
  info: ["M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z", "M12 11v5", "M12 8h.01"],
  menu: ["M4 7h16", "M4 12h16", "M4 17h16"],
  close: ["M6 6l12 12", "M18 6L6 18"],
};

const state = {
  cluster: null,
  ai: { enabled: false, status: "disabled", provider: "", model: "" },
  remediation: { enabled: false, approval_required: true },
  investigations: null,
  remediations: null,
  detail: null,
  proposals: [],
  remediationDetail: null,
  loadError: null,
  ready: false,
  updatedAt: null,
  notice: "",
  saving: false,
  navOpen: false,
  collapsed: false,
  scrollTop: false,
  focusId: "",
  focusPos: null,
  filters: { status: "", severity: "", issue: "", resource: "", q: "" },
  remFilters: { status: "", q: "" },
};

try {
  state.collapsed = localStorage.getItem("kubemedic.sidebar") === "collapsed";
} catch (error) {
  state.collapsed = false;
}

applyDocument();
onLocale(() => render());
window.addEventListener("popstate", () => render());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.navOpen) {
    state.navOpen = false;
    render();
  }
});

boot();

async function boot() {
  render();
  await refresh(false);
  window.setInterval(() => {
    refresh(true);
  }, 20000);
}

async function refresh(soft) {
  if (soft && interactionOpen()) return;
  try {
    const [cluster, ai, remediation, investigations, remediations] = await Promise.all([
      getJson("/api/v1/cluster/status"),
      getJson("/api/v1/ai/status").catch(() => state.ai),
      getJson("/api/v1/remediation/status").catch(() => state.remediation),
      getJson("/api/v1/investigations"),
      getJson("/api/v1/remediations").catch(() => state.remediations || []),
    ]);
    state.cluster = cluster;
    state.ai = ai;
    state.remediation = remediation;
    state.investigations = investigations;
    state.remediations = remediations;
    state.updatedAt = new Date();
    state.loadError = null;
    await loadRoute();
  } catch (error) {
    if (!soft || !state.investigations) state.loadError = error;
  } finally {
    state.ready = true;
    render();
  }
}

async function loadRoute() {
  const current = route();
  if (current.page === "investigation") {
    state.detail = await getJson("/api/v1/investigations/" + encodeURIComponent(current.id));
    state.proposals = await getJson(
      "/api/v1/investigations/" + encodeURIComponent(current.id) + "/remediations",
    ).catch(() => []);
  }
  if (current.page === "remediation") {
    state.remediationDetail = await getJson("/api/v1/remediations/" + encodeURIComponent(current.id));
  }
}

function interactionOpen() {
  if (document.querySelector("dialog[open]")) return true;
  if (state.saving) return true;
  const active = document.activeElement;
  return Boolean(active && active.id && active.id.startsWith("filter-"));
}

function render() {
  const y = state.scrollTop ? 0 : window.scrollY;
  state.scrollTop = false;
  const root = document.querySelector("#app");
  root.replaceChildren(skipLink(), shell());
  window.scrollTo(0, y);
  if (state.focusId) {
    const next = document.getElementById(state.focusId);
    if (next) {
      next.focus();
      if (state.focusPos != null && next.setSelectionRange) {
        next.setSelectionRange(state.focusPos, state.focusPos);
      }
    }
    state.focusId = "";
    state.focusPos = null;
  }
}

function shell() {
  const frame = element("div", "shell" + (state.collapsed ? " collapsed" : "") + (state.navOpen ? " nav-open" : ""));
  frame.append(scrim(), sidebar(), column());
  if (state.notice) frame.append(toast(state.notice));
  return frame;
}

function skipLink() {
  const link = document.createElement("a");
  link.className = "skip";
  link.href = "#main";
  link.textContent = t("skip");
  return link;
}

function scrim() {
  const button = element("button", "scrim");
  button.type = "button";
  button.setAttribute("aria-label", t("header.closeMenu"));
  button.addEventListener("click", () => {
    state.navOpen = false;
    render();
  });
  return button;
}

function sidebar() {
  const aside = element("aside", "sidebar");
  const brand = element("div", "brand");
  const name = element("strong");
  name.textContent = t("appName");
  const sub = element("span", "muted");
  sub.textContent = state.cluster && state.cluster.namespace ? state.cluster.namespace : "";
  brand.append(name, sub);
  const nav = element("nav", "nav");
  nav.setAttribute("aria-label", t("appName"));
  const items = [
    ["/", "overview", "nav.overview"],
    ["/investigations", "investigations", "nav.investigations"],
    ["/remediations", "remediation", "nav.remediations"],
    ["/observability", "observability", "nav.observability"],
    ["/system", "system", "nav.system"],
  ];
  const current = route();
  for (const [href, iconName, key] of items) {
    const link = document.createElement("a");
    link.href = href;
    link.append(icon(iconName), labelSpan(t(key)));
    if (isCurrent(href, current)) link.setAttribute("aria-current", "page");
    link.addEventListener("click", (event) => follow(event, href));
    nav.append(link);
  }
  const collapse = element("button", "collapse-button");
  collapse.type = "button";
  collapse.append(icon(state.collapsed ? "menu" : "close"), labelSpan(state.collapsed ? t("header.expand") : t("header.collapse"), "collapse-label"));
  collapse.setAttribute("aria-label", state.collapsed ? t("header.expand") : t("header.collapse"));
  collapse.addEventListener("click", () => {
    state.collapsed = !state.collapsed;
    try {
      localStorage.setItem("kubemedic.sidebar", state.collapsed ? "collapsed" : "expanded");
    } catch (error) {
      /* ignore */
    }
    render();
  });
  aside.append(brand, nav, collapse);
  return aside;
}

function labelSpan(value, className) {
  const span = element("span", className || "nav-label");
  span.textContent = value;
  return span;
}

function column() {
  const wrap = element("div", "column");
  wrap.append(topbar(), main());
  return wrap;
}

function topbar() {
  const bar = element("header", "topbar");
  const left = element("div", "top-group");
  const menu = element("button", "menu-button");
  menu.type = "button";
  menu.append(icon("menu"));
  menu.setAttribute("aria-label", state.navOpen ? t("header.closeMenu") : t("header.menu"));
  menu.setAttribute("aria-expanded", state.navOpen ? "true" : "false");
  menu.addEventListener("click", () => {
    state.navOpen = !state.navOpen;
    render();
  });
  const brand = element("strong");
  brand.textContent = t("appName");
  left.append(menu, brand, clusterChip());
  bar.append(left, languageSwitcher());
  return bar;
}

function clusterChip() {
  const chip = element("p", "status-chip");
  const connected = state.cluster && state.cluster.status === "connected";
  chip.classList.add(connected ? "ok" : "bad");
  chip.append(icon(connected ? "check" : "alert"));
  const label = element("span");
  const name = state.cluster && state.cluster.namespace ? state.cluster.namespace : "taskflow";
  label.textContent = `${t("header.kubernetes")}: ${connected ? t("cluster.connected") : t("cluster.disconnected")} · ${name}`;
  chip.append(label);
  return chip;
}

function languageSwitcher() {
  const group = element("div", "lang");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", t("header.language"));
  for (const choice of localeChoices()) {
    const button = element("button", "lang-button");
    button.type = "button";
    button.textContent = choice.label;
    button.setAttribute("lang", choice.code);
    button.setAttribute("aria-pressed", getLocale() === choice.code ? "true" : "false");
    button.addEventListener("click", () => setLocale(choice.code));
    group.append(button);
  }
  return group;
}

function main() {
  const region = element("main", "main");
  region.id = "main";
  region.tabIndex = -1;
  region.append(page());
  return region;
}

function page() {
  const current = route();
  if (!state.ready) return loadingBlock(t("loading.page"));
  if (state.loadError && !state.investigations && current.page !== "remediation") {
    return errorState(t("errors.generic"), state.loadError);
  }
  if (current.page === "investigations") return investigationsPage();
  if (current.page === "investigation") return investigationPage(current.id);
  if (current.page === "remediations") return remediationsPage();
  if (current.page === "remediation") return remediationPage(current.id);
  if (current.page === "observability") return observabilityPage();
  if (current.page === "system") return systemPage();
  return overviewPage();
}

function overviewPage() {
  const wrap = element("div", "stack");
  const active = activeItems();
  const critical = active.filter((item) => item.severity === "critical" || item.severity === "high").length;
  wrap.append(pageHeader(t("pages.overview"), refreshButton()));
  wrap.append(lead(active.length, critical));
  wrap.append(statGrid(active, critical));
  wrap.append(safetyNotes());
  wrap.append(serviceHealth());
  wrap.append(activeSection(active));
  const resolved = (state.investigations || []).filter((item) => item.status === "resolved").slice(0, 5);
  if (resolved.length) {
    const section = element("section", "section");
    section.append(heading("h2", t("overview.recent")), investigationTable(resolved, false));
    wrap.append(section);
  }
  return wrap;
}

function lead(count, critical) {
  const box = element("div", "lead " + (count ? "attn" : "ok"));
  box.append(icon(count ? "alert" : "check"));
  const copy = element("div");
  const title = element("strong");
  title.textContent = count
    ? t(count === 1 ? "overview.leadActive" : "overview.leadActivePlural", { count })
    : t("overview.noActive");
  const body = element("p", "hint");
  body.textContent = count && critical
    ? `${t("overview.criticalHigh")}: ${critical}`
    : count
      ? ""
      : t("overview.noActiveBody");
  copy.append(title, body);
  box.append(copy);
  return box;
}

function statGrid(active, critical) {
  const grid = element("section", "stats");
  grid.setAttribute("aria-label", t("pages.overview"));
  const connected = state.cluster && state.cluster.status === "connected";
  const openCount = active.filter((item) => item.status === "open").length;
  grid.append(statCard(t("overview.active"), String(active.length), openCount ? "bad" : active.length ? "warn" : "ok"));
  grid.append(statCard(t("overview.recovering"), String(active.filter((item) => item.status === "recovering").length), active.some((item) => item.status === "recovering") ? "warn" : ""));
  grid.append(statCard(t("overview.resolved"), String((state.investigations || []).filter((item) => item.status === "resolved").length), ""));
  grid.append(statCard(t("overview.criticalHigh"), String(critical), critical ? "bad" : "ok"));
  grid.append(statCard(t("overview.kubernetes"), connected ? t("cluster.connected") : t("cluster.disconnected"), connected ? "ok" : "warn", true));
  grid.append(statCard(t("overview.remediation"), state.remediation.enabled ? t("health.enabled") : t("health.disabled"), "neutral", true));
  grid.append(statCard(t("overview.ai"), state.ai.enabled ? t("health.enabled") : t("health.disabled"), "neutral", true));
  return grid;
}

function statCard(label, value, tone, word) {
  const card = element("div", "stat" + (tone ? " " + tone : ""));
  const name = element("span");
  name.textContent = label;
  const number = element("strong", word ? "word" : "");
  number.textContent = value;
  card.setAttribute("aria-label", `${label}: ${value}`);
  card.append(name, number);
  return card;
}

function safetyNotes() {
  const wrap = element("div", "stack");
  if (!state.remediation.enabled) wrap.append(callout(t("remediation.disabled"), t("remediation.disabledBody"), "neutral"));
  if (!state.ai.enabled) wrap.append(callout(t("detail.aiDisabled"), t("detail.aiDisabledBody"), "neutral"));
  return wrap;
}

function serviceHealth() {
  const section = element("section", "section");
  section.append(heading("h2", t("overview.serviceHealth")));
  const hint = element("p", "hint");
  hint.textContent = t("overview.serviceHint");
  const list = element("div", "stack");
  for (const row of healthRows()) list.append(healthCard(row));
  section.append(hint, list);
  return section;
}

function healthRows() {
  const connected = state.cluster && state.cluster.status === "connected";
  return [
    workloadRow("health.taskflowApi", /taskflow-api/),
    workloadRow("health.taskflowFrontend", /taskflow-frontend/),
    workloadRow("health.postgresql", /postgres/),
    { name: t("health.kubemedic"), state: "healthy", detail: t("health.apiOk") },
    {
      name: t("health.kubernetes"),
      state: connected ? "connected" : "disconnected",
      detail: state.cluster ? state.cluster.namespace : "taskflow",
    },
    { name: t("health.prometheus"), state: "notChecked", detail: t("health.labLink"), href: LINKS.prometheus, link: t("health.openPrometheus") },
    { name: t("health.grafana"), state: "notChecked", detail: t("health.labLink"), href: LINKS.grafanaTaskflow, link: t("health.openGrafana") },
  ];
}

function workloadRow(nameKey, pattern) {
  const items = (state.investigations || []).filter((item) => pattern.test(item.resource_name || ""));
  const open = items.some((item) => item.status === "open");
  const recovering = items.some((item) => item.status === "recovering");
  if (open) return { name: t(nameKey), state: "degraded", detail: t("health.activeOn") };
  if (recovering) return { name: t(nameKey), state: "recovering", detail: t("status.recovering") };
  return { name: t(nameKey), state: "healthy", detail: t("health.noActive") };
}

function healthCard(row) {
  const card = element("article", "card health-row");
  const copy = element("div");
  const title = element("h3");
  title.textContent = row.name;
  const detail = element("p", "hint");
  detail.textContent = row.detail || "";
  copy.append(title, detail);
  if (row.href) {
    const link = document.createElement("a");
    link.href = row.href;
    link.textContent = row.link;
    link.target = "_blank";
    link.rel = "noreferrer";
    copy.append(link);
  }
  card.append(copy, healthBadge(row.state));
  return card;
}

function healthBadge(value) {
  const tone = {
    healthy: "ok",
    connected: "ok",
    recovering: "recovering",
    degraded: "high",
    unhealthy: "critical",
    disconnected: "warn",
    unavailable: "warn",
    disabled: "neutral",
    notChecked: "neutral",
  }[value] || "neutral";
  return badge(t("health." + value), tone, value === "healthy" || value === "connected" ? "check" : value === "disabled" || value === "notChecked" ? "info" : "alert");
}

function activeSection(active) {
  const section = element("section", "section");
  section.append(heading("h2", t("overview.activeTitle")));
  if (!active.length) {
    section.append(emptyState(t("overview.noActive"), t("overview.noActiveBody")));
    return section;
  }
  section.append(investigationTable(active, false));
  return section;
}

function investigationsPage() {
  const wrap = element("div", "stack");
  if (state.loadError && !state.investigations) return errorState(t("errors.investigations"), state.loadError);
  wrap.append(pageHeader(t("pages.investigations"), refreshButton()));
  wrap.append(updatedLine());
  wrap.append(investigationFilters());
  const items = filteredInvestigations();
  if (!(state.investigations || []).length) {
    wrap.append(emptyState(t("empty.investigations"), t("overview.noActiveBody")));
    return wrap;
  }
  if (!items.length) {
    wrap.append(emptyState(t("empty.filters"), t("filters.clear")));
    return wrap;
  }
  wrap.append(investigationTable(items, true));
  return wrap;
}

function investigationFilters() {
  const bar = element("div", "filters");
  bar.append(
    selectFilter("status", t("filters.status"), ["", "open", "recovering", "resolved"], state.filters.status, (value) => statusLabel(value)),
    selectFilter("severity", t("filters.severity"), ["", "critical", "high", "medium", "low"], state.filters.severity, (value) => severityLabel(value)),
    selectFilter("issue", t("filters.issue"), ["", ...issueOptions()], state.filters.issue, (value) => (value ? issueName(value) : t("filters.all"))),
    selectFilter("resource", t("filters.resource"), ["", ...resourceOptions()], state.filters.resource, (value) => value || t("filters.all")),
    searchFilter(),
    clearButton(),
  );
  return bar;
}

function selectFilter(key, label, values, current, display) {
  const wrap = document.createElement("label");
  wrap.className = "filter";
  const caption = element("span");
  caption.textContent = label;
  const control = document.createElement("select");
  control.id = "filter-" + key;
  control.name = key;
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value ? display(value) : t("filters.all");
    option.selected = value === current;
    control.append(option);
  }
  control.addEventListener("change", () => {
    state.filters[key] = control.value;
    render();
  });
  wrap.append(caption, control);
  return wrap;
}

function searchFilter() {
  const wrap = document.createElement("label");
  wrap.className = "filter";
  const caption = element("span");
  caption.textContent = t("filters.search");
  const input = document.createElement("input");
  input.id = "filter-q";
  input.name = "q";
  input.type = "search";
  input.value = state.filters.q;
  input.placeholder = t("filters.searchPlaceholder");
  input.addEventListener("input", () => {
    state.filters.q = input.value;
    state.focusId = input.id;
    state.focusPos = input.selectionStart;
    render();
  });
  wrap.append(caption, input);
  return wrap;
}

function clearButton() {
  const button = element("button", "button ghost");
  button.type = "button";
  button.textContent = t("filters.clear");
  button.addEventListener("click", () => {
    state.filters = { status: "", severity: "", issue: "", resource: "", q: "" };
    notify(t("notice.filters"));
    render();
  });
  return button;
}

function investigationTable(items, withMobile) {
  const wrap = element("div");
  const tableWrap = element("div", "table-wrap");
  const table = document.createElement("table");
  const caption = document.createElement("caption");
  caption.className = "hint";
  caption.textContent = t("pages.investigations");
  const head = document.createElement("thead");
  const row = document.createElement("tr");
  for (const key of ["id", "issue", "resource", "severity", "status", "detected", "updated", "source"]) {
    const cell = document.createElement("th");
    cell.textContent = t("columns." + key);
    row.append(cell);
  }
  head.append(row);
  const body = document.createElement("tbody");
  for (const item of items) body.append(investigationRow(item));
  table.append(caption, head, body);
  tableWrap.append(table);
  wrap.append(tableWrap);
  if (withMobile || true) wrap.append(mobileCards(items));
  return wrap;
}

function investigationRow(item) {
  const row = document.createElement("tr");
  row.append(
    cellLink(item.id, "/investigations/" + encodeURIComponent(item.id), true),
    textCell(issueName(item.detected_issue), item.detected_issue),
    textCell(item.resource_name, item.resource_kind),
    badgeCell(severityBadge(item.severity)),
    badgeCell(statusBadge(item.status)),
    plainCell(formatWhen(item.created_at)),
    plainCell(formatWhen(item.updated_at)),
    plainCell(sourceLabel(item)),
  );
  return row;
}

function mobileCards(items) {
  const list = element("div", "mobile-list");
  for (const item of items) {
    const card = element("article", "card stack");
    const top = element("div", "card-top");
    const id = document.createElement("a");
    id.className = "mono";
    id.href = "/investigations/" + encodeURIComponent(item.id);
    id.textContent = item.id;
    id.addEventListener("click", (event) => follow(event, id.href));
    const badges = element("div", "inline");
    badges.append(severityBadge(item.severity), statusBadge(item.status));
    top.append(id, badges);
    const issue = element("h3");
    issue.textContent = issueName(item.detected_issue);
    const technical = element("p", "mono hint");
    technical.textContent = item.detected_issue;
    const resource = element("p");
    resource.textContent = `${item.resource_kind} ${item.resource_name}`;
    const when = element("p", "hint");
    when.textContent = `${t("columns.updated")} ${formatWhen(item.updated_at)}`;
    card.append(top, issue, technical, resource, sourceBadge(item), when);
    list.append(card);
  }
  return list;
}

function investigationPage(id) {
  if (state.loadError && !state.detail) return errorState(t("errors.investigation"), state.loadError);
  const item = state.detail && state.detail.id === id ? state.detail : null;
  if (!item) return emptyState(t("detail.notFound", { id }), "");
  const wrap = element("article", "stack");
  wrap.append(crumbs([
    ["/", t("detail.backOverview")],
    ["/investigations", t("detail.backInvestigations")],
    ["", item.id],
  ]));
  wrap.append(detailHeader(item));
  wrap.append(sectionBlock(t("detail.what"), paragraph(explainIssue(item))));
  wrap.append(sectionBlock(t("detail.current"), statusBadge(item.status), paragraph(t("current." + item.status) || statusLabel(item.status))));
  wrap.append(causeBlock(item));
  wrap.append(evidenceBlock(item));
  wrap.append(timelineBlock(item.timeline || []));
  wrap.append(remediationSection(item, state.proposals || []));
  wrap.append(aiSection(item));
  wrap.append(resolutionBlock(item));
  wrap.append(technicalBlock(item));
  return wrap;
}

function detailHeader(item) {
  const head = element("header", "stack");
  const top = element("div", "card-top");
  const titles = element("div", "stack");
  const id = element("p", "mono");
  id.textContent = item.id;
  const h = element("h1");
  h.textContent = issueName(item.detected_issue);
  const reason = element("p", "mono hint");
  reason.textContent = `${t("detail.reason")}: ${item.detected_issue}`;
  titles.append(id, h, reason);
  const badges = element("div", "inline");
  badges.append(severityBadge(item.severity), statusBadge(item.status));
  top.append(titles, badges);
  const facts = element("p");
  facts.textContent = `${item.resource_kind} ${item.namespace}/${item.resource_name} · ${t("detail.detected")} ${formatWhen(item.created_at)}`;
  head.append(top, facts, refreshButton(() => notify(t("notice.refreshed"))));
  return head;
}

function causeBlock(item) {
  const rule = item.rule_analysis && item.rule_analysis.likely_root_cause ? item.rule_analysis : item;
  const section = element("section", "panel stack");
  section.append(heading("h2", t("detail.cause")));
  const note = element("p", "hint");
  note.textContent = t("detail.causeNote");
  const label = element("p", "meta");
  label.textContent = t("detail.rules");
  section.append(note, label, paragraph(phrase(rule.likely_root_cause || item.likely_root_cause || "")));
  const actions = rule.recommended_actions || item.recommended_actions || [];
  if (actions.length) {
    section.append(heading("h3", t("detail.recommended")));
    const list = document.createElement("ol");
    for (const action of actions) {
      const li = document.createElement("li");
      li.textContent = phrase(action);
      list.append(li);
    }
    section.append(list);
  }
  return section;
}

function evidenceBlock(item) {
  const section = element("section", "panel stack");
  section.append(heading("h2", t("detail.evidence")));
  const evidence = item.evidence || [];
  const primary = evidence.filter((entry) => PRIMARY_EVIDENCE.includes(entry.label));
  if (!primary.length) section.append(paragraph(t("detail.noEvidence")));
  else section.append(factList(primary));
  return section;
}

function timelineBlock(items) {
  const section = element("section", "panel stack");
  section.id = "timeline";
  section.append(heading("h2", t("detail.timeline")));
  if (!items.length) {
    section.append(paragraph(t("detail.noTimeline")));
    return section;
  }
  const list = element("ol", "timeline");
  items.forEach((entry, index) => {
    const row = document.createElement("li");
    const time = document.createElement("time");
    time.dateTime = entry.at || "";
    time.textContent = formatClock(entry.at);
    time.title = formatExact(entry.at);
    const mark = element("div", "mark-col");
    mark.append(element("span", "dot"), element("span", "stem"));
    const copy = element("div", "event-copy");
    const message = element("p");
    message.textContent = phrase(entry.message);
    copy.append(message);
    if (index === items.length - 1) copy.append(element("span"));
    row.append(time, mark, copy);
    list.append(row);
  });
  section.append(list);
  return section;
}

function remediationSection(item, proposals) {
  const section = element("section", "panel stack");
  section.id = "remediation";
  section.append(heading("h2", t("detail.remediation")));
  section.append(paragraph(t("remediation.safety")));
  if (!state.remediation.enabled) section.append(callout(t("remediation.disabled"), t("remediation.disabledBody"), "neutral"));
  if (!proposals.length) {
    section.append(emptyState(t("detail.noProposal"), ""));
    return section;
  }
  for (const proposal of proposals) section.append(proposalSummary(item.id, proposal));
  return section;
}

function proposalSummary(investigationId, proposal) {
  const card = element("article", "card stack");
  const top = element("div", "proposal-head");
  const id = document.createElement("a");
  id.className = "mono";
  id.href = "/remediations/" + encodeURIComponent(proposal.id);
  id.textContent = proposal.id;
  id.addEventListener("click", (event) => follow(event, id.href));
  top.append(id, statusBadge(proposal.status));
  const action = element("p");
  action.textContent = actionLabel(proposal.action);
  const target = element("p", "mono");
  target.textContent = `${proposal.namespace}/${proposal.target_name}`;
  const why = element("p");
  why.textContent = phrase(proposal.reason);
  card.append(top, action, target, why);
  if (!state.remediation.enabled) card.append(paragraph(t("remediation.recordedDisabled")));
  else if (proposal.status === "proposed") {
    const row = element("div", "inline");
    row.append(approveButton(investigationId, proposal), cancelProposalButton(investigationId, proposal));
    card.append(row);
  } else if (proposal.status === "approved") {
    card.append(cancelProposalButton(investigationId, proposal));
  }
  return card;
}

function aiSection(item) {
  const section = element("section", "panel stack");
  section.id = "ai";
  section.append(heading("h2", t("detail.ai")));
  const note = element("p", "hint");
  note.textContent = t("detail.aiOptional");
  section.append(note);
  const analysis = item.ai_analysis;
  if (item.ai_status === "ok" && analysis) {
    section.append(paragraph(analysis.summary || ""));
    if (analysis.likely_root_cause) section.append(paragraph(analysis.likely_root_cause));
    section.append(stringList(t("detail.supporting"), analysis.supporting_evidence));
    section.append(stringList(t("detail.recommended"), analysis.recommended_actions));
    if (analysis.confidence) {
      section.append(paragraph(`${t("detail.confidence")}: ${analysis.confidence}. ${analysis.confidence_explanation || ""}`));
    }
    return section;
  }
  if (!state.ai.enabled || item.ai_status === "disabled" || !item.ai_status) {
    section.append(callout(t("detail.aiDisabled"), t("detail.aiDisabledBody"), "neutral"));
    return section;
  }
  section.append(callout(t("detail.aiUnavailable"), t("detail.aiUnavailableBody"), "neutral"));
  if (state.ai.enabled) section.append(aiButton(item.id));
  return section;
}

function resolutionBlock(item) {
  const section = element("section", "panel stack");
  section.append(heading("h2", t("detail.resolution")));
  if (item.status !== "resolved") {
    section.append(paragraph(t("detail.noResolution")));
    section.append(resolveButton(item.id));
    return section;
  }
  section.append(paragraph(phrase(item.resolution_reason || "")));
  const when = element("p", "hint");
  when.textContent = formatWhen(item.resolved_at);
  section.append(when);
  if (item.recovery_duration_seconds != null) {
    const duration = element("p", "hint");
    duration.textContent = String(item.recovery_duration_seconds) + "s";
    section.append(duration);
  }
  return section;
}

function technicalBlock(item) {
  const details = document.createElement("details");
  details.className = "technical";
  const summary = document.createElement("summary");
  summary.textContent = t("detail.showTechnical");
  const inside = element("div", "inside");
  inside.append(factList(item.evidence || []));
  inside.append(eventsBlock(item));
  inside.append(logsBlock(item));
  const exact = element("div", "stack");
  exact.append(heading("h3", t("detail.exactTime")));
  exact.append(paragraph(`${t("columns.detected")} ${formatExact(item.created_at)}`));
  exact.append(paragraph(`${t("columns.updated")} ${formatExact(item.updated_at)}`));
  inside.append(exact);
  details.append(summary, inside);
  return details;
}

function eventsBlock(item) {
  const section = element("div", "stack");
  section.append(heading("h3", t("detail.events")));
  if (!(item.events || []).length) {
    section.append(paragraph(t("detail.noEvents")));
    return section;
  }
  for (const event of item.events) {
    const row = element("div", "event");
    const reason = element("strong", "mono");
    reason.textContent = `${event.reason} (${event.count})`;
    const message = element("p");
    message.textContent = event.message;
    row.append(reason, message);
    section.append(row);
  }
  return section;
}

function logsBlock(item) {
  const section = element("div", "stack");
  section.append(heading("h3", t("detail.logs")));
  if (!(item.logs || []).length) {
    section.append(paragraph(t("detail.noLogs")));
    return section;
  }
  for (const entry of item.logs) {
    const label = element("p", "hint");
    label.textContent = entry.source === "previous" ? t("detail.previousLogs") : t("detail.currentLogs");
    const pre = document.createElement("pre");
    pre.textContent = entry.content;
    section.append(label, pre);
  }
  return section;
}

function remediationsPage() {
  const wrap = element("div", "stack");
  if (state.loadError && !state.remediations) return errorState(t("errors.remediations"), state.loadError);
  wrap.append(pageHeader(t("pages.remediations"), refreshButton()));
  if (!state.remediation.enabled) wrap.append(callout(t("remediation.disabled"), t("remediation.disabledBody"), "neutral"));
  const items = filteredRemediations();
  if (!(state.remediations || []).length) {
    wrap.append(emptyState(t("remediation.none"), t("remediation.safety")));
    return wrap;
  }
  if (!items.length) {
    wrap.append(emptyState(t("remediation.noneMatch"), ""));
    return wrap;
  }
  wrap.append(remediationTable(items));
  return wrap;
}

function filteredRemediations() {
  const query = state.remFilters.q.trim().toLowerCase();
  return (state.remediations || []).filter((item) => {
    if (state.remFilters.status && item.status !== state.remFilters.status) return false;
    if (!query) return true;
    const blob = `${item.id} ${item.investigation_id} ${item.action} ${item.target_name}`.toLowerCase();
    return blob.includes(query);
  });
}

function remediationTable(items) {
  const wrap = element("div");
  const tableWrap = element("div", "table-wrap");
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const row = document.createElement("tr");
  for (const key of ["id", "id", "action", "target", "status", "approver", "created", "verified"]) {
    const cell = document.createElement("th");
    cell.textContent = key === "id" && row.childElementCount === 0 ? t("columns.id") : key === "id" ? t("columns.id") : t("columns." + key);
    row.append(cell);
  }
  row.children[1].textContent = t("nav.investigations");
  head.append(row);
  const body = document.createElement("tbody");
  for (const item of items) {
    const line = document.createElement("tr");
    line.append(
      cellLink(item.id, "/remediations/" + encodeURIComponent(item.id), true),
      cellLink(item.investigation_id, "/investigations/" + encodeURIComponent(item.investigation_id), true),
      plainCell(actionLabel(item.action)),
      plainCell(`${item.namespace}/${item.target_name}`),
      badgeCell(statusBadge(item.status)),
      plainCell(item.approved_by || "—"),
      plainCell(formatWhen(item.created_at)),
      plainCell(item.verified_at ? formatWhen(item.verified_at) : "—"),
    );
    body.append(line);
  }
  table.append(head, body);
  tableWrap.append(table);
  const cards = element("div", "mobile-list");
  for (const item of items) {
    const card = element("article", "card stack");
    const link = document.createElement("a");
    link.className = "mono";
    link.href = "/remediations/" + encodeURIComponent(item.id);
    link.textContent = item.id;
    link.addEventListener("click", (event) => follow(event, link.href));
    card.append(link, statusBadge(item.status), paragraph(actionLabel(item.action)), paragraph(`${item.namespace}/${item.target_name}`));
    const inv = document.createElement("a");
    inv.href = "/investigations/" + encodeURIComponent(item.investigation_id);
    inv.textContent = item.investigation_id;
    inv.addEventListener("click", (event) => follow(event, inv.href));
    card.append(inv);
    cards.append(card);
  }
  wrap.append(tableWrap, cards);
  return wrap;
}

function remediationPage(id) {
  const item = state.remediationDetail && state.remediationDetail.id === id ? state.remediationDetail : null;
  if (!item) {
    if (state.loadError) return errorState(t("errors.remediations"), state.loadError);
    return emptyState(t("remediation.notFound", { id }), "");
  }
  const wrap = element("article", "stack");
  wrap.append(crumbs([
    ["/", t("detail.backOverview")],
    ["/remediations", t("pages.remediations")],
    ["", item.id],
  ]));
  const head = element("header", "card-top");
  const titles = element("div");
  const title = element("h1", "mono");
  title.textContent = item.id;
  const action = element("p");
  action.textContent = actionLabel(item.action);
  titles.append(title, action);
  head.append(titles, statusBadge(item.status));
  wrap.append(head);
  if (!state.remediation.enabled) wrap.append(callout(t("remediation.disabled"), t("remediation.disabledBody"), "neutral"));
  wrap.append(sectionBlock(t("remediation.recommended"), paragraph(actionLabel(item.action))));
  wrap.append(sectionBlock(t("remediation.why"), paragraph(phrase(item.reason))));
  wrap.append(sectionBlock(t("remediation.target"), paragraph(`${item.namespace}/${item.target_name}`)));
  const inv = document.createElement("a");
  inv.href = "/investigations/" + encodeURIComponent(item.investigation_id);
  inv.textContent = item.investigation_id;
  inv.addEventListener("click", (event) => follow(event, inv.href));
  wrap.append(sectionBlock(t("remediation.openInvestigation"), inv));
  wrap.append(sectionBlock(t("remediation.policy"), paragraph(t("remediation.policyBody"))));
  wrap.append(approvalBlock(item));
  wrap.append(sectionBlock(t("remediation.execution"), paragraph(item.executed_at ? formatWhen(item.executed_at) : t("remediation.notExecuted"))));
  wrap.append(sectionBlock(t("remediation.verification"), paragraph(item.verified_at ? `${t("status.verified")} · ${formatWhen(item.verified_at)}` : t("remediation.notVerified"))));
  if (item.result) wrap.append(sectionBlock(t("detail.resolution"), paragraph(phrase(item.result))));
  if (item.error) wrap.append(callout(t("status.failed"), item.error, "warn"));
  wrap.append(compareBlock(item));
  wrap.append(auditTrail(item));
  if (state.remediation.enabled && item.status === "proposed") {
    wrap.append(approveButton(item.investigation_id, item));
  }
  return wrap;
}

function approvalBlock(item) {
  const section = element("section", "panel stack");
  section.append(heading("h2", t("remediation.human")));
  if (!item.approved_by) {
    section.append(paragraph(t("remediation.notApproved")));
    return section;
  }
  section.append(paragraph(`${item.approved_by} · ${formatWhen(item.approved_at)}`));
  if (item.approval_reason) section.append(paragraph(item.approval_reason));
  return section;
}

function compareBlock(item) {
  const section = element("section", "panel stack");
  section.append(heading("h2", t("remediation.audit")));
  const grid = element("div", "compare");
  grid.append(snapshotCard(t("remediation.before"), item.before_state), snapshotCard(t("remediation.after"), item.after_state));
  section.append(grid);
  return section;
}

function snapshotCard(title, snapshot) {
  const card = element("div", "stack");
  card.append(heading("h3", title));
  if (!snapshot || !Object.keys(snapshot).length) {
    card.append(paragraph(t("remediation.emptySnapshot")));
    return card;
  }
  const list = document.createElement("dl");
  list.className = "facts";
  for (const [key, labelKey] of AUDIT_FIELDS) {
    if (snapshot[key] == null) continue;
    const term = document.createElement("dt");
    term.textContent = t(labelKey);
    const value = document.createElement("dd");
    value.className = "mono";
    value.textContent = Array.isArray(snapshot[key]) ? snapshot[key].join(", ") : String(snapshot[key]);
    list.append(term, value);
  }
  card.append(list);
  return card;
}

function auditTrail(item) {
  const details = document.createElement("details");
  details.className = "technical";
  const summary = document.createElement("summary");
  summary.textContent = t("detail.showTechnical");
  const inside = element("div", "inside");
  inside.append(timelineBlock((item.transitions || []).map((entry) => ({
    at: entry.at,
    message: entry.reason || entry.status,
  }))));
  const raw = document.createElement("pre");
  raw.textContent = JSON.stringify({ before: item.before_state, after: item.after_state }, null, 2);
  inside.append(raw);
  details.append(summary, inside);
  return details;
}

function observabilityPage() {
  const wrap = element("div", "stack");
  wrap.append(pageHeader(t("pages.observability")));
  wrap.append(paragraph(t("observability.intro")));
  wrap.append(linkCard(t("observability.prometheus"), t("observability.notProbed"), LINKS.prometheus, t("health.openPrometheus")));
  wrap.append(linkCard(t("observability.grafana"), t("health.labLink"), LINKS.grafanaTaskflow, t("health.openGrafana")));
  wrap.append(linkCard(t("observability.taskflow"), t("health.metricsHint"), LINKS.grafanaTaskflow, t("health.metricsTaskflow")));
  wrap.append(linkCard(t("observability.kubemedic"), t("health.metricsHint"), LINKS.grafanaKubemedic, t("health.metricsKubemedic")));
  return wrap;
}

function linkCard(title, detail, href, linkText) {
  const card = element("article", "card stack");
  card.append(heading("h2", title), healthBadge("notChecked"), paragraph(detail));
  const link = document.createElement("a");
  link.href = href;
  link.textContent = linkText;
  link.target = "_blank";
  link.rel = "noreferrer";
  card.append(link);
  return card;
}

function systemPage() {
  const wrap = element("div", "stack");
  wrap.append(pageHeader(t("pages.system"), refreshButton()));
  wrap.append(paragraph(t("system.intro")));
  const connected = state.cluster && state.cluster.status === "connected";
  const rows = [
    { name: t("health.kubernetes"), state: connected ? "connected" : "disconnected", detail: state.cluster ? `${state.cluster.namespace} · ${state.cluster.mode || ""}` : "" },
    { name: t("health.watcher"), state: connected ? "connected" : "unavailable", detail: t("health.watcherDetail") },
    workloadRow("health.taskflowApi", /taskflow-api/),
    workloadRow("health.taskflowFrontend", /taskflow-frontend/),
    workloadRow("health.postgresql", /postgres/),
    { name: t("health.prometheus"), state: "notChecked", detail: t("health.labLink") },
    { name: t("health.ai"), state: state.ai.enabled ? "connected" : "disabled", detail: state.ai.enabled ? `${state.ai.provider || ""} ${state.ai.model || ""}` : t("detail.aiDisabledBody") },
    { name: t("health.remediation"), state: state.remediation.enabled ? "connected" : "disabled", detail: state.remediation.enabled ? t("remediation.human") : t("remediation.disabledBody") },
  ];
  for (const row of rows) wrap.append(healthCard(row));
  return wrap;
}

function approveButton(investigationId, proposal) {
  const button = element("button", "button primary");
  button.type = "button";
  button.textContent = t("approveButton." + proposal.action) || t("remediation.approve");
  button.addEventListener("click", () => openApproval(investigationId, proposal));
  return button;
}

function openApproval(investigationId, proposal) {
  const dialog = document.createElement("dialog");
  dialog.className = "confirm";
  const body = element("form", "dialog-body");
  const title = element("h2");
  title.id = "approve-title";
  title.textContent = t("approveTitle." + proposal.action) || t("remediation.human");
  dialog.setAttribute("aria-labelledby", "approve-title");
  const target = element("p");
  target.textContent = `${t("remediation.target")}: ${proposal.namespace}/${proposal.target_name}`;
  const action = element("p");
  action.textContent = `${t("columns.action")}: ${actionLabel(proposal.action)}`;
  const reason = element("p");
  reason.textContent = `${t("remediation.why")}: ${phrase(proposal.reason)}`;
  const warning = element("p");
  warning.textContent = t("remediation.willModify");
  const name = labeledInput("approved-by", t("remediation.approvedBy"), "text");
  name.input.required = true;
  name.input.autocomplete = "username";
  name.input.pattern = "[A-Za-z0-9][A-Za-z0-9_.@-]{0,63}";
  const hint = element("p", "hint");
  hint.textContent = t("remediation.nameHint");
  const note = labeledInput("approval-note", t("remediation.approvalNote"), "textarea");
  note.input.maxLength = 280;
  const error = element("p", "hint");
  error.setAttribute("role", "alert");
  const actions = element("div", "dialog-actions");
  const cancel = element("button", "button ghost");
  cancel.type = "button";
  cancel.textContent = t("common.cancel");
  cancel.addEventListener("click", () => dialog.close());
  const confirm = element("button", "button primary");
  confirm.type = "submit";
  confirm.textContent = t("approveButton." + proposal.action) || t("remediation.approve");
  actions.append(cancel, confirm);
  body.append(title, target, action, reason, warning, name.field, hint, note.field, error, actions);
  body.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.saving) return;
    state.saving = true;
    confirm.disabled = true;
    cancel.disabled = true;
    try {
      await postJson("/api/v1/remediations/" + encodeURIComponent(proposal.id) + "/approve", {
        approved_by: name.input.value,
        reason: note.input.value,
        confirm: true,
      });
      dialog.close();
      notify(t("notice.approved"));
      await refresh(false);
    } catch (failure) {
      state.saving = false;
      confirm.disabled = false;
      cancel.disabled = false;
      error.textContent = t("notice.approveFailed");
      const extra = element("span", "mono");
      extra.textContent = failure.message ? " " + failure.message : "";
      error.append(extra);
    }
  });
  dialog.addEventListener("close", () => {
    state.saving = false;
    dialog.remove();
  });
  dialog.append(body);
  document.body.append(dialog);
  dialog.showModal();
  name.input.focus();
}

function cancelProposalButton(investigationId, proposal) {
  const button = element("button", "button ghost");
  button.type = "button";
  button.textContent = t("remediation.cancelProposal");
  button.addEventListener("click", () => {
    confirmDialog({
      title: t("remediation.cancelTitle"),
      body: t("remediation.cancelBody"),
      confirmLabel: t("remediation.confirmCancel"),
      onConfirm: async () => {
        await postJson("/api/v1/remediations/" + encodeURIComponent(proposal.id) + "/cancel", {});
        notify(t("notice.cancelled"));
        await refresh(false);
      },
      failure: t("notice.cancelFailed"),
    });
  });
  return button;
}

function resolveButton(id) {
  const button = element("button", "button ghost");
  button.type = "button";
  button.textContent = t("detail.markResolved");
  button.addEventListener("click", () => {
    confirmDialog({
      title: t("detail.resolveTitle"),
      body: t("detail.resolveBody"),
      confirmLabel: t("detail.confirmResolve"),
      onConfirm: async () => {
        await postJson("/api/v1/investigations/" + encodeURIComponent(id) + "/resolve", {});
        notify(t("notice.resolved"));
        await refresh(false);
      },
      failure: t("notice.resolveFailed"),
    });
  });
  return button;
}

function aiButton(id) {
  const button = element("button", "button ghost");
  button.type = "button";
  button.textContent = t("detail.runAi");
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await postJson("/api/v1/investigations/" + encodeURIComponent(id) + "/ai/analyze", {});
      await refresh(false);
    } catch (error) {
      button.disabled = false;
      notify(t("notice.aiFailed"));
    }
  });
  return button;
}

function confirmDialog({ title, body, confirmLabel, onConfirm, failure }) {
  const dialog = document.createElement("dialog");
  dialog.className = "confirm";
  const form = element("form", "dialog-body");
  const headingNode = element("h2");
  headingNode.id = "confirm-title";
  headingNode.textContent = title;
  dialog.setAttribute("aria-labelledby", "confirm-title");
  const copy = element("p");
  copy.textContent = body;
  const error = element("p", "hint");
  error.setAttribute("role", "alert");
  const actions = element("div", "dialog-actions");
  const cancel = element("button", "button ghost");
  cancel.type = "button";
  cancel.textContent = t("common.cancel");
  cancel.addEventListener("click", () => dialog.close());
  const confirm = element("button", "button primary");
  confirm.type = "submit";
  confirm.textContent = confirmLabel;
  actions.append(cancel, confirm);
  form.append(headingNode, copy, error, actions);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.saving) return;
    state.saving = true;
    confirm.disabled = true;
    try {
      await onConfirm();
      dialog.close();
    } catch (problem) {
      state.saving = false;
      confirm.disabled = false;
      error.textContent = failure || problem.message;
    }
  });
  dialog.addEventListener("close", () => {
    state.saving = false;
    dialog.remove();
  });
  dialog.append(form);
  document.body.append(dialog);
  dialog.showModal();
  cancel.focus();
}

function pageHeader(title, extra) {
  const header = element("div", "page-head");
  header.append(heading("h1", title));
  if (extra) header.append(extra);
  return header;
}

function refreshButton(after) {
  const button = element("button", "button ghost");
  button.type = "button";
  button.textContent = t("common.refresh");
  button.addEventListener("click", async () => {
    button.disabled = true;
    await refresh(false);
    if (after) after();
  });
  return button;
}

function updatedLine() {
  const line = element("p", "hint");
  line.textContent = state.updatedAt ? `${t("common.lastUpdated")} ${formatWhen(state.updatedAt)}` : "";
  return line;
}

function sectionBlock(title, ...nodes) {
  const section = element("section", "panel stack");
  section.append(heading("h2", title), ...nodes);
  return section;
}

function heading(tag, value) {
  const node = element(tag);
  node.textContent = value;
  return node;
}

function paragraph(value) {
  const node = element("p");
  node.textContent = value || "";
  return node;
}

function callout(title, body, tone) {
  const box = element("div", "callout " + (tone || "neutral"));
  const strong = element("strong");
  strong.textContent = title;
  const copy = element("p");
  copy.textContent = body;
  box.append(strong, copy);
  return box;
}

function emptyState(title, body) {
  const box = element("div", "empty stack");
  const strong = element("strong");
  strong.textContent = title;
  box.append(strong);
  if (body) box.append(paragraph(body));
  return box;
}

function errorState(title, error) {
  const box = element("div", "error-state stack");
  box.setAttribute("role", "alert");
  const strong = element("strong");
  strong.textContent = title;
  const retry = element("button", "button primary");
  retry.type = "button";
  retry.textContent = t("common.retry");
  retry.addEventListener("click", () => refresh(false));
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = t("errors.technical");
  const pre = document.createElement("pre");
  pre.textContent = error && error.message ? error.message : String(error || "");
  details.append(summary, pre);
  box.append(strong, retry, details);
  return box;
}

function loadingBlock(label) {
  const wrap = element("div", "stack");
  wrap.setAttribute("role", "status");
  wrap.setAttribute("aria-live", "polite");
  const text = element("p");
  text.textContent = label;
  wrap.append(text, element("div", "skeleton"), element("div", "skeleton"), element("div", "skeleton"));
  return wrap;
}

function crumbs(parts) {
  const nav = element("nav", "crumbs");
  nav.setAttribute("aria-label", t("detail.backOverview"));
  parts.forEach((part, index) => {
    if (index) nav.append(document.createTextNode(" / "));
    if (!part[0]) {
      const current = element("span", "mono");
      current.textContent = part[1];
      nav.append(current);
      return;
    }
    const link = document.createElement("a");
    link.href = part[0];
    link.textContent = part[1];
    link.addEventListener("click", (event) => follow(event, part[0]));
    nav.append(link);
  });
  return nav;
}

function factList(entries) {
  const list = document.createElement("dl");
  list.className = "facts";
  for (const entry of entries) {
    const term = document.createElement("dt");
    term.textContent = phrase(entry.label);
    const value = document.createElement("dd");
    value.className = "mono";
    value.textContent = entry.value;
    list.append(term, value);
  }
  return list;
}

function stringList(title, values) {
  const section = element("div", "stack");
  section.append(heading("h3", title));
  const list = document.createElement("ul");
  for (const value of values || []) {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  }
  if (!list.childNodes.length) section.append(paragraph(t("common.none")));
  else section.append(list);
  return section;
}

function labeledInput(id, label, kind) {
  const field = document.createElement("label");
  field.htmlFor = id;
  field.textContent = label;
  const input = kind === "textarea" ? document.createElement("textarea") : document.createElement("input");
  input.id = id;
  input.name = id;
  if (kind !== "textarea") input.type = kind;
  field.append(input);
  return { field, input };
}

function badge(text, tone, iconName) {
  const node = element("span", "badge " + tone);
  if (iconName) node.append(icon(iconName));
  const label = element("span");
  label.textContent = text;
  node.append(label);
  return node;
}

function statusBadge(value) {
  const tone = {
    open: "open",
    recovering: "recovering",
    resolved: "resolved",
    proposed: "proposed",
    approved: "approved",
    executing: "executing",
    succeeded: "succeeded",
    failed: "failed",
    verified: "verified",
    cancelled: "cancelled",
  }[value] || "neutral";
  const iconName = value === "resolved" || value === "verified" || value === "succeeded" ? "check" : value === "failed" ? "alert" : "info";
  return badge(statusLabel(value), tone, iconName);
}

function severityBadge(value) {
  const tone = value || "informational";
  const iconName = value === "critical" || value === "high" ? "alert" : value === "low" ? "check" : "info";
  return badge(severityLabel(value), tone, iconName);
}

function sourceBadge(item) {
  return badge(sourceLabel(item), "neutral", "info");
}

function statusLabel(value) {
  if (!value) return t("filters.all");
  const key = "status." + value;
  const label = t(key);
  return label === key ? value : label;
}

function severityLabel(value) {
  const key = "severity." + (value || "informational");
  const label = t(key);
  return label === key ? value : label;
}

function sourceLabel(item) {
  if (item.analysis_source === "rules+ai") return t("source.both");
  return t("source.rules");
}

function issueName(issue) {
  const key = "issues." + issue;
  const label = t(key);
  return label === key ? issue : label;
}

function explainIssue(item) {
  const key = "explain." + item.detected_issue;
  const label = t(key);
  if (label !== key) return label;
  return phrase(item.summary || "");
}

function actionLabel(action) {
  const key = "actions." + action;
  const label = t(key);
  return label === key ? action : label;
}

function activeItems() {
  return sortInvestigations((state.investigations || []).filter((item) => item.status === "open" || item.status === "recovering"));
}

function filteredInvestigations() {
  const filters = state.filters;
  const query = filters.q.trim().toLowerCase();
  return sortInvestigations((state.investigations || []).filter((item) => {
    if (filters.status && item.status !== filters.status) return false;
    if (filters.severity && item.severity !== filters.severity) return false;
    if (filters.issue && item.detected_issue !== filters.issue) return false;
    if (filters.resource && item.resource_name !== filters.resource) return false;
    if (!query) return true;
    const blob = `${item.id} ${item.resource_name} ${item.detected_issue} ${issueName(item.detected_issue)}`.toLowerCase();
    return blob.includes(query);
  }));
}

function sortInvestigations(items) {
  const rank = { open: 0, recovering: 1, resolved: 2 };
  return [...items].sort((a, b) => (rank[a.status] ?? 9) - (rank[b.status] ?? 9) || String(b.updated_at).localeCompare(String(a.updated_at)));
}

function issueOptions() {
  const found = new Set((state.investigations || []).map((item) => item.detected_issue));
  return ISSUE_TYPES.filter((issue) => found.has(issue)).concat([...found].filter((issue) => !ISSUE_TYPES.includes(issue)));
}

function resourceOptions() {
  return [...new Set((state.investigations || []).map((item) => item.resource_name).filter(Boolean))].sort();
}

function cellLink(value, href, mono) {
  const cell = document.createElement("td");
  const link = document.createElement("a");
  link.href = href;
  link.textContent = value;
  if (mono) link.className = "mono";
  link.addEventListener("click", (event) => follow(event, href));
  cell.append(link);
  return cell;
}

function textCell(primary, secondary) {
  const cell = document.createElement("td");
  const main = element("div");
  main.textContent = primary;
  cell.append(main);
  if (secondary) {
    const sub = element("div", "mono hint");
    sub.textContent = secondary;
    cell.append(sub);
  }
  return cell;
}

function plainCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function badgeCell(node) {
  const cell = document.createElement("td");
  cell.append(node);
  return cell;
}

function toast(message) {
  const node = element("p", "toast");
  node.setAttribute("role", "status");
  node.textContent = message;
  return node;
}

function notify(message) {
  state.notice = message;
  window.setTimeout(() => {
    if (state.notice === message) {
      state.notice = "";
      render();
    }
  }, 3500);
}

function follow(event, href) {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
  event.preventDefault();
  if (location.pathname !== href) history.pushState({}, "", href);
  state.navOpen = false;
  state.detail = null;
  state.remediationDetail = null;
  state.scrollTop = true;
  refresh(false);
}

function route() {
  const path = location.pathname;
  if (path === "/investigations") return { page: "investigations" };
  const investigation = path.match(/^\/investigations\/(INV-\d+)$/);
  if (investigation) return { page: "investigation", id: investigation[1] };
  if (path === "/remediations") return { page: "remediations" };
  const remediation = path.match(/^\/remediations\/(REM-\d+)$/);
  if (remediation) return { page: "remediation", id: remediation[1] };
  if (path === "/observability") return { page: "observability" };
  if (path === "/system") return { page: "system" };
  return { page: "overview" };
}

function isCurrent(href, current) {
  if (href === "/") return current.page === "overview";
  if (href === "/investigations") return current.page === "investigations" || current.page === "investigation";
  if (href === "/remediations") return current.page === "remediations" || current.page === "remediation";
  return location.pathname === href;
}

function icon(name) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("icon");
  for (const path of ICONS[name] || ICONS.info) {
    const node = document.createElementNS(SVG, "path");
    node.setAttribute("d", path);
    node.setAttribute("fill", "none");
    node.setAttribute("stroke", "currentColor");
    node.setAttribute("stroke-width", "1.8");
    node.setAttribute("stroke-linecap", "round");
    node.setAttribute("stroke-linejoin", "round");
    svg.append(node);
  }
  return svg;
}

function element(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = new Error("Request failed (" + response.status + ")");
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!response.ok) {
    let detail = "Request failed (" + response.status + ")";
    try {
      const payload = await response.json();
      if (payload && payload.detail) detail = String(payload.detail);
    } catch (error) {
      detail = "Request failed (" + response.status + ")";
    }
    const failure = new Error(detail);
    failure.status = response.status;
    throw failure;
  }
  if (response.status === 204) return null;
  return response.json();
}
