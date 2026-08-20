function fillList(node, items, render) {
  node.innerHTML = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "none";
    node.appendChild(empty);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = render(item);
    node.appendChild(li);
  }
}

function funnelPct(part, whole) {
  const denom = whole > 0 ? whole : 1;
  const pct = Math.round(((Number(part) || 0) / denom) * 100);
  if (pct < 0) {
    return 0;
  }
  if (pct > 100) {
    return 100;
  }
  return pct;
}

function fillSearchProgress(host, nTrials, planned) {
  host.innerHTML = "";
  const n = Number(nTrials) || 0;
  const plan = Number(planned) || 0;
  const label = document.createElement("span");
  label.className = "search-progress-label";
  label.textContent = "search: " + n + " / " + plan;
  const track = document.createElement("span");
  track.className = "search-progress";
  const fill = document.createElement("span");
  fill.className = "search-progress-fill";
  const pct = funnelPct(n, plan);
  fill.dataset.pct = String(pct);
  fill.style.width = pct + "%";
  track.appendChild(fill);
  host.appendChild(label);
  host.appendChild(track);
}

function appendFunnelSeg(stack, key, count, whole) {
  const seg = document.createElement("span");
  seg.className = "funnel-seg";
  seg.dataset.key = key;
  const pct = funnelPct(count, whole);
  seg.dataset.pct = String(pct);
  seg.style.width = pct + "%";
  stack.appendChild(seg);
}

function fillFunnelStack(host, funnel) {
  host.innerHTML = "";
  const evaluated = funnel.n_evaluated || 0;
  const passed = funnel.n_passed || 0;
  const failed = funnel.n_failed || 0;
  const incomplete = funnel.n_incomplete || 0;
  if (evaluated + passed + failed + incomplete <= 0) {
    return;
  }
  const stack = document.createElement("div");
  stack.className = "funnel-stack";
  const whole = evaluated > 0 ? evaluated : passed + failed + incomplete;
  appendFunnelSeg(stack, "passed", passed, whole);
  appendFunnelSeg(stack, "failed", failed, whole);
  appendFunnelSeg(stack, "incomplete", incomplete, whole);
  host.appendChild(stack);
}

function fillFunnel(job) {
  const funnel = job.funnel || {};
  const evaluated = funnel.n_evaluated || 0;
  const passed = funnel.n_passed || 0;
  const failed = funnel.n_failed || 0;
  const incomplete = funnel.n_incomplete || 0;
  document.getElementById("funnel-summary").textContent = [
    "evaluated: " + evaluated,
    "passed: " + passed,
    "failed: " + failed,
    "incomplete: " + incomplete,
  ].join(" · ");
  fillFunnelStack(document.getElementById("funnel-bars"), funnel);
  const node = document.getElementById("funnel");
  const names = funnel.dominant_failures;
  const counts = funnel.failure_counts || {};
  node.innerHTML = "";
  if (!names || names.length === 0) {
    const empty = document.createElement("li");
    empty.textContent = "none";
    node.appendChild(empty);
    return;
  }
  names.forEach(function (name) {
    const count = counts[name] || 0;
    const li = document.createElement("li");
    li.className = "funnel-fail";
    const label = document.createElement("span");
    label.textContent = name + " × " + count;
    const track = document.createElement("span");
    track.className = "funnel-fail-track";
    const fill = document.createElement("span");
    fill.className = "funnel-fail-fill";
    const pct = funnelPct(count, failed);
    fill.dataset.pct = String(pct);
    fill.style.width = pct + "%";
    track.appendChild(fill);
    li.appendChild(label);
    li.appendChild(track);
    node.appendChild(li);
  });
}

function fillQualifying(job) {
  const node = document.getElementById("qualifying");
  node.innerHTML = "";
  const rows = job.qualifying_candidates || [];
  if (!rows.length) {
    const empty = document.createElement("li");
    empty.textContent = "none";
    node.appendChild(empty);
    return;
  }
  const canExport = job.research_outcome === "FOUND";
  rows.forEach(function (row) {
    const li = document.createElement("li");
    li.className = "qualifying-item";
    const trial = row.trial_id || "gates.json";
    const text = document.createElement("span");
    text.textContent =
      trial + " · " + (row.kind || "") + " · " + formatGridRow(row.parameters);
    li.appendChild(text);
    if (canExport && trial.indexOf("c_") === 0) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "export-asb";
      button.textContent = "Export .asb";
      button.addEventListener("click", function () {
        exportCandidate(trial);
      });
      li.appendChild(button);
    }
    node.appendChild(li);
  });
}

async function exportCandidate(candidateId) {
  const status = document.getElementById("export-status");
  if (!currentRunId || !candidateId) {
    status.textContent = "Export needs a selected job and candidate.";
    return;
  }
  const response = await fetch(
    "/v1/jobs/" + encodeURIComponent(currentRunId) + "/export",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: candidateId }),
    }
  );
  const body = await response.json();
  if (!response.ok) {
    status.textContent = body.error || "export failed";
    return;
  }
  status.textContent = body.exported_path || "";
}

function fillQueued(job) {
  const node = document.getElementById("queued");
  node.innerHTML = "";
  const items = job.queued_hypotheses || [];
  if (!items.length) {
    const empty = document.createElement("li");
    empty.textContent = "none";
    node.appendChild(empty);
    return;
  }
  items.forEach(function (row) {
    const li = document.createElement("li");
    li.className = "queued-item";
    const text = document.createElement("span");
    text.textContent = row.statement || JSON.stringify(row);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "load-queued";
    button.textContent = "Load into editor";
    button.addEventListener("click", function () {
      loadQueuedHypothesis(row, job);
    });
    li.appendChild(text);
    li.appendChild(button);
    node.appendChild(li);
  });
}

function fillNextStep(job) {
  const node = document.getElementById("next-step");
  node.innerHTML = "";
  const items = job.queued_hypotheses || [];
  if (!items.length) {
    return;
  }
  const row = items[0];
  const text = document.createElement("span");
  text.textContent = "Next run: " + (row.statement || "");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "load-queued";
  button.textContent = "Load into editor";
  button.addEventListener("click", function () {
    loadQueuedHypothesis(row, job);
  });
  node.appendChild(text);
  node.appendChild(button);
}

function fillHandoff(job) {
  const node = document.getElementById("handoff");
  node.innerHTML = "";
  const rows = job.qualifying_candidates || [];
  if (job.research_outcome !== "FOUND" || !rows.length) {
    return;
  }
  const row = rows[0];
  const trial = row.trial_id || "gates.json";
  const text = document.createElement("span");
  text.textContent =
    "Qualifying: " +
    trial +
    " · " +
    (row.kind || "") +
    " · " +
    formatGridRow(row.parameters);
  node.appendChild(text);
  if (trial.indexOf("c_") === 0) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "export-asb";
    button.textContent = "Export .asb";
    button.addEventListener("click", function () {
      exportCandidate(trial);
    });
    node.appendChild(button);
  }
}

function datasetYaml(job) {
  const ds = job && job.dataset;
  if (!ds || !ds.dataset_id || !ds.sha256) {
    return "";
  }
  return (
    "dataset:\n  dataset_id: " +
    ds.dataset_id +
    "\n  sha256: " +
    ds.sha256 +
    "\n"
  );
}

function loadQueuedHypothesis(row, job) {
  syncingForm = true;
  document.getElementById("field-statement").value = row.statement || "";
  document.getElementById("field-economic-logic").value = row.economic_logic || "";
  document.getElementById("field-signal-mechanism").value =
    row.signal_mechanism || "";
  document.getElementById("field-market-scope").value = row.market_scope || "";
  document.getElementById("field-market-profile").value =
    row.market_profile || "";
  document.getElementById("field-benchmark").value = row.benchmark || "";
  if (job) {
    if (!document.getElementById("field-seed").value && job.seed != null) {
      document.getElementById("field-seed").value = String(job.seed);
    }
    if (
      !document.getElementById("field-time-budget").value &&
      job.time_budget_s != null
    ) {
      document.getElementById("field-time-budget").value = String(job.time_budget_s);
    }
    if (
      !document.getElementById("field-cost-budget").value &&
      job.cost_budget_usd != null
    ) {
      document.getElementById("field-cost-budget").value = String(
        job.cost_budget_usd
      );
    }
  }
  const selected = {};
  (row.hard_gates || []).forEach(function (name) {
    selected[name] = true;
  });
  Array.prototype.forEach.call(
    document.querySelectorAll("#field-hard-gates input[type='checkbox']"),
    function (box) {
      box.checked = Boolean(selected[box.value]);
    }
  );
  let yaml = formToYaml();
  if (!extractDatasetYaml(yaml)) {
    yaml += datasetYaml(job);
  }
  document.getElementById("spec-yaml").value = yaml;
  syncingForm = false;
  previewedYaml = null;
  setSubmitEnabled(false);
  previewProtocol();
}

const EXAMPLE_SPEC =
  "statement: 12-1 momentum works in US large caps net of costs\n" +
  "economic_logic: past winners continue\n" +
  "signal_mechanism: momentum_12_1\n" +
  "market_scope: AAPL, MSFT\n" +
  "market_profile: us-equity-daily\n" +
  "benchmark: SPY\n" +
  "hard_gates: [dsr, walk_forward, vs_benchmark]\n" +
  "seed: 7\n" +
  "time_budget_s: 3600\n" +
  "cost_budget_usd: 5.0\n";

let currentRunId = null;
let syncingForm = false;

function unquoteYaml(value) {
  const text = String(value || "").trim();
  if (
    (text.startsWith('"') && text.endsWith('"')) ||
    (text.startsWith("'") && text.endsWith("'"))
  ) {
    return text.slice(1, -1);
  }
  return text;
}

function extractDatasetYaml(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const captured = [];
  let capturing = false;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (/^dataset\s*:/.test(line)) {
      capturing = true;
      captured.push(line);
      continue;
    }
    if (capturing) {
      if (/^[A-Za-z_]/.test(line)) {
        break;
      }
      captured.push(line);
    }
  }
  while (captured.length && captured[captured.length - 1].trim() === "") {
    captured.pop();
  }
  if (!captured.length) {
    return "";
  }
  return captured.join("\n") + "\n";
}

function parseSpecYaml(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const values = {};
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$/);
    if (!match) {
      i += 1;
      continue;
    }
    const key = match[1];
    const rest = match[2];
    if (key === "dataset") {
      i += 1;
      while (
        i < lines.length &&
        (lines[i].startsWith(" ") ||
          lines[i].startsWith("\t") ||
          lines[i].trim() === "")
      ) {
        i += 1;
      }
      continue;
    }
    if (key === "hard_gates") {
      if (rest.startsWith("[")) {
        const inner = rest.replace(/^\[/, "").replace(/\]\s*$/, "");
        values.hard_gates = inner
          .split(",")
          .map(function (item) {
            return unquoteYaml(item);
          })
          .filter(Boolean);
        i += 1;
        continue;
      }
      const items = [];
      i += 1;
      while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
        items.push(unquoteYaml(lines[i].replace(/^\s*-\s+/, "")));
        i += 1;
      }
      values.hard_gates = items;
      continue;
    }
    values[key] = unquoteYaml(rest);
    i += 1;
  }
  return values;
}

function formToYaml() {
  const dataset = extractDatasetYaml(document.getElementById("spec-yaml").value);
  const gates = Array.prototype.map
    .call(
      document.querySelectorAll("#field-hard-gates input[type='checkbox']:checked"),
      function (box) {
        return box.value;
      }
    )
    .join(", ");
  const lines = [
    "statement: " + document.getElementById("field-statement").value,
    "economic_logic: " + document.getElementById("field-economic-logic").value,
    "signal_mechanism: " + document.getElementById("field-signal-mechanism").value,
    "market_scope: " + document.getElementById("field-market-scope").value,
    "market_profile: " + document.getElementById("field-market-profile").value,
    "benchmark: " + document.getElementById("field-benchmark").value,
    "hard_gates: [" + gates + "]",
    "seed: " + document.getElementById("field-seed").value,
    "time_budget_s: " + document.getElementById("field-time-budget").value,
    "cost_budget_usd: " + document.getElementById("field-cost-budget").value,
  ];
  return lines.join("\n") + "\n" + dataset;
}

function yamlToForm(text) {
  const parsed = parseSpecYaml(text);
  syncingForm = true;
  document.getElementById("field-statement").value = parsed.statement || "";
  document.getElementById("field-economic-logic").value =
    parsed.economic_logic || "";
  document.getElementById("field-signal-mechanism").value =
    parsed.signal_mechanism || "";
  document.getElementById("field-market-scope").value = parsed.market_scope || "";
  document.getElementById("field-market-profile").value =
    parsed.market_profile || "";
  document.getElementById("field-benchmark").value = parsed.benchmark || "";
  document.getElementById("field-seed").value = parsed.seed || "";
  document.getElementById("field-time-budget").value = parsed.time_budget_s || "";
  document.getElementById("field-cost-budget").value =
    parsed.cost_budget_usd || "";
  const selected = {};
  (parsed.hard_gates || []).forEach(function (name) {
    selected[name] = true;
  });
  Array.prototype.forEach.call(
    document.querySelectorAll("#field-hard-gates input[type='checkbox']"),
    function (box) {
      box.checked = Boolean(selected[box.value]);
    }
  );
  syncingForm = false;
}

function formatGridRow(row) {
  if (!row) {
    return "{}";
  }
  const keys = Object.keys(row);
  if (keys.length === 0) {
    return "{}";
  }
  keys.sort();
  return keys
    .map(function (key) {
      return key + "=" + row[key];
    })
    .join(" ");
}

function renderPreview(body) {
  const preview = document.getElementById("protocol-preview");
  preview.textContent = "";
  const summary = document.createElement("div");
  summary.textContent = [
    "spec_id: " + body.spec_id,
    "statement: " + body.statement,
    "signal_mechanism: " + body.signal_mechanism,
    "hard_gates: " + (body.hard_gates || []).join(", "),
    "planned_n_trials: " + body.planned_n_trials,
    "grid:",
  ].join("\n");
  preview.appendChild(summary);
  const grid = document.createElement("ul");
  grid.id = "protocol-grid";
  (body.method_parameter_grid || []).forEach(function (row) {
    const item = document.createElement("li");
    item.textContent = formatGridRow(row);
    grid.appendChild(item);
  });
  preview.appendChild(grid);
}

function addJobSpan(button, className, text) {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text;
  button.appendChild(span);
}

function fillOutcomeGloss(outcome) {
  const sources = {
    FOUND: "help-found",
    NO_EVIDENCE: "help-no-evidence",
    INCONCLUSIVE: "help-inconclusive",
    NONE: "help-status",
  };
  const src = document.getElementById(sources[outcome] || "help-status");
  const gloss = document.getElementById("outcome-gloss");
  gloss.textContent = src ? src.textContent : "";
}

function fillPrimaryEvidence(job) {
  const node = document.getElementById("primary-evidence");
  const value = job.primary_evidence;
  node.textContent = value
    ? "Primary evidence: " + value
    : "Primary evidence: (running or not yet terminal)";
}

function fillReport(job) {
  const node = document.getElementById("report");
  node.textContent = job.report_markdown || "";
}

async function showJob(runId) {
  currentRunId = runId;
  const response = await fetch("/v1/jobs/" + encodeURIComponent(runId));
  const job = await response.json();
  const detail = document.getElementById("detail");
  detail.hidden = false;
  const verdict = document.getElementById("verdict");
  const outcome = document.getElementById("outcome");
  verdict.dataset.outcome = job.research_outcome;
  outcome.dataset.outcome = job.research_outcome;
  outcome.textContent = job.research_outcome;
  fillOutcomeGloss(job.research_outcome);
  fillPrimaryEvidence(job);
  fillNextStep(job);
  fillHandoff(job);
  document.getElementById("job-status").textContent = "Job status: " + job.status;
  const statement =
    job.hypothesis && job.hypothesis.statement ? job.hypothesis.statement : "";
  document.getElementById("hypothesis-statement").textContent = statement;
  document.getElementById("spec-meta").textContent =
    "spec_id: " +
    job.spec_id +
    " · seed: " +
    job.seed +
    " · n_trials: " +
    job.n_trials +
    " · planned_n_trials: " +
    job.planned_n_trials;
  fillSearchProgress(
    document.getElementById("search-progress"),
    job.n_trials,
    job.planned_n_trials
  );
  document.getElementById("stop-reason").textContent = job.stop_reason
    ? "Stop reason: " + job.stop_reason
    : "Stop reason: (running or not yet terminal)";
  fillReport(job);
  const cancel = document.getElementById("cancel-job");
  const resume = document.getElementById("resume-job");
  cancel.hidden = job.status !== "queued" && job.status !== "running";
  resume.hidden = job.status !== "failed";
  const results = (job.evidence && job.evidence.results) || [];
  const evidenceItems =
    job.evidence_lines && job.evidence_lines.length
      ? job.evidence_lines
      : results;
  fillQualifying(job);
  fillList(document.getElementById("evidence"), evidenceItems, function (row) {
    if (typeof row === "string") {
      return row;
    }
    return row.name + ": " + (row.passed ? "pass" : "fail");
  });
  fillFunnel(job);
  fillList(document.getElementById("revisions"), job.revisions, function (row) {
    return (
      (row.trial_id || "") +
      " · " +
      (row.revision || "") +
      " · " +
      formatGridRow(row.parameters)
    );
  });
  fillQueued(job);
}

async function postJobAction(action) {
  if (!currentRunId) {
    return;
  }
  await fetch(
    "/v1/jobs/" + encodeURIComponent(currentRunId) + "/" + action,
    { method: "POST" }
  );
  await loadJobs();
  await showJob(currentRunId);
}

async function loadJobs() {
  const response = await fetch("/v1/jobs");
  const data = await response.json();
  const jobs = data.jobs || [];
  const ids = {};
  jobs.forEach(function (job) {
    ids[job.run_id] = true;
  });
  if (!currentRunId || !ids[currentRunId]) {
    currentRunId = jobs.length ? jobs[0].run_id : null;
  }
  const list = document.getElementById("job-list");
  list.innerHTML = "";
  for (const job of jobs) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.runId = job.run_id;
    button.dataset.status = job.status;
    button.dataset.outcome = job.research_outcome;
    if (job.run_id === currentRunId) {
      button.setAttribute("aria-current", "true");
    }
    const statement =
      job.hypothesis && job.hypothesis.statement ? job.hypothesis.statement : "";
    const meta = document.createElement("span");
    meta.className = "job-meta";
    addJobSpan(meta, "job-id", job.run_id);
    addJobSpan(meta, "job-status", job.status);
    addJobSpan(meta, "job-outcome", job.research_outcome);
    button.appendChild(meta);
    addJobSpan(button, "job-statement", statement);
    addJobSpan(button, "job-trials", "n_trials: " + job.n_trials);
    const progress = document.createElement("span");
    progress.className = "job-search-progress";
    fillSearchProgress(progress, job.n_trials, job.planned_n_trials);
    button.appendChild(progress);
    const mini = document.createElement("span");
    mini.className = "job-funnel";
    fillFunnelStack(mini, job.funnel || {});
    button.appendChild(mini);
    button.addEventListener("click", function () {
      showJob(job.run_id);
    });
    item.appendChild(button);
    list.appendChild(item);
  }
  const detail = document.getElementById("detail");
  if (currentRunId) {
    await showJob(currentRunId);
  } else {
    detail.hidden = true;
  }
}

let previewedYaml = null;

function yamlMatchesPreview() {
  return (
    previewedYaml !== null &&
    document.getElementById("spec-yaml").value === previewedYaml
  );
}

function setSubmitEnabled(enabled) {
  document.getElementById("submit-job").disabled = !enabled;
}

async function previewProtocol() {
  const errors = document.getElementById("preflight-errors");
  const preview = document.getElementById("protocol-preview");
  const constraint = document.getElementById("host-constraint");
  errors.textContent = "";
  preview.textContent = "";
  setSubmitEnabled(false);
  previewedYaml = null;
  const yamlText = document.getElementById("spec-yaml").value;
  const response = await fetch("/v1/jobs/preview", {
    method: "POST",
    headers: { "Content-Type": "application/yaml" },
    body: yamlText,
  });
  const body = await response.json();
  if (!response.ok) {
    errors.textContent = body.error || "preview failed";
    return;
  }
  if (body.host_constraint) {
    constraint.textContent = body.host_constraint;
  }
  renderPreview(body);
  if (!body.ok) {
    errors.textContent = (body.errors || []).join("; ");
    return;
  }
  previewedYaml = yamlText;
  setSubmitEnabled(true);
}

async function submitJob() {
  if (!yamlMatchesPreview()) {
    setSubmitEnabled(false);
    return;
  }
  const errors = document.getElementById("preflight-errors");
  const constraint = document.getElementById("host-constraint");
  errors.textContent = "";
  const response = await fetch("/v1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/yaml" },
    body: document.getElementById("spec-yaml").value,
  });
  const body = await response.json();
  if (!response.ok) {
    const list = body.errors || [body.error || "submit failed"];
    errors.textContent = list.join("; ");
    return;
  }
  if (body.host_constraint) {
    constraint.textContent = body.host_constraint;
  }
  currentRunId = body.run_id;
  await loadJobs();
}

document.getElementById("load-example").addEventListener("click", function () {
  const box = document.getElementById("spec-yaml");
  box.value = EXAMPLE_SPEC;
  yamlToForm(EXAMPLE_SPEC);
  box.dispatchEvent(new Event("input"));
});

document.getElementById("preview-protocol").addEventListener("click", function () {
  previewProtocol();
});

document.getElementById("submit-job").addEventListener("click", function () {
  submitJob();
});

document.getElementById("cancel-job").addEventListener("click", function () {
  postJobAction("cancel");
});

document.getElementById("resume-job").addEventListener("click", function () {
  postJobAction("resume");
});

document.getElementById("spec-yaml").addEventListener("input", function () {
  if (!syncingForm) {
    yamlToForm(document.getElementById("spec-yaml").value);
  }
  setSubmitEnabled(yamlMatchesPreview());
});

document.getElementById("hypothesis-form").addEventListener("input", function () {
  if (syncingForm) {
    return;
  }
  syncingForm = true;
  document.getElementById("spec-yaml").value = formToYaml();
  syncingForm = false;
  setSubmitEnabled(yamlMatchesPreview());
});

document.getElementById("hypothesis-form").addEventListener("change", function () {
  if (syncingForm) {
    return;
  }
  syncingForm = true;
  document.getElementById("spec-yaml").value = formToYaml();
  syncingForm = false;
  setSubmitEnabled(yamlMatchesPreview());
});

setInterval(loadJobs, 2000);

loadJobs();
