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

async function showJob(runId) {
  currentRunId = runId;
  const response = await fetch("/v1/jobs/" + encodeURIComponent(runId));
  const job = await response.json();
  const detail = document.getElementById("detail");
  detail.hidden = false;
  const outcome = document.getElementById("outcome");
  outcome.dataset.outcome = job.research_outcome;
  outcome.textContent = job.research_outcome;
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
    job.n_trials;
  document.getElementById("stop-reason").textContent = job.stop_reason
    ? "Stop reason: " + job.stop_reason
    : "Stop reason: (running or not yet terminal)";
  const cancel = document.getElementById("cancel-job");
  const resume = document.getElementById("resume-job");
  cancel.hidden = job.status !== "queued" && job.status !== "running";
  resume.hidden = job.status !== "failed";
  const results = (job.evidence && job.evidence.results) || [];
  const evidenceItems =
    job.evidence_lines && job.evidence_lines.length
      ? job.evidence_lines
      : results;
  fillList(document.getElementById("evidence"), evidenceItems, function (row) {
    if (typeof row === "string") {
      return row;
    }
    return row.name + ": " + (row.passed ? "pass" : "fail");
  });
  fillList(
    document.getElementById("funnel"),
    job.funnel && job.funnel.dominant_failures,
    function (name) {
      const counts = (job.funnel && job.funnel.failure_counts) || {};
      const count = counts[name];
      return count ? name + " × " + count : name;
    }
  );
  const funnel = job.funnel || {};
  document.getElementById("funnel-summary").textContent = [
    "evaluated: " + (funnel.n_evaluated || 0),
    "passed: " + (funnel.n_passed || 0),
    "failed: " + (funnel.n_failed || 0),
  ].join(" · ");
  fillList(document.getElementById("revisions"), job.revisions, function (row) {
    return (
      (row.trial_id || "") +
      " · " +
      (row.revision || "") +
      " · " +
      formatGridRow(row.parameters)
    );
  });
  fillList(document.getElementById("queued"), job.queued_hypotheses, function (row) {
    return row.statement || JSON.stringify(row);
  });
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
  const list = document.getElementById("job-list");
  list.innerHTML = "";
  for (const job of data.jobs || []) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.runId = job.run_id;
    button.dataset.status = job.status;
    button.dataset.outcome = job.research_outcome;
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
    button.addEventListener("click", function () {
      showJob(job.run_id);
    });
    item.appendChild(button);
    list.appendChild(item);
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
  loadJobs();
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
