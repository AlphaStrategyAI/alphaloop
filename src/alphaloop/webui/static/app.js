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
      return name;
    }
  );
  fillList(document.getElementById("revisions"), job.revisions, function (row) {
    return (row.trial_id || "") + " " + (row.revision || "");
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
    button.textContent = job.run_id + " — " + job.status + " — " + job.research_outcome;
    button.dataset.status = job.status;
    button.dataset.outcome = job.research_outcome;
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
  preview.textContent =
    "spec_id: " +
    body.spec_id +
    " · planned_n_trials: " +
    body.planned_n_trials +
    " · signal_mechanism: " +
    body.signal_mechanism +
    " · hard_gates: " +
    (body.hard_gates || []).join(",") +
    " · grid: " +
    JSON.stringify(body.method_parameter_grid);
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
  setSubmitEnabled(yamlMatchesPreview());
});

setInterval(loadJobs, 2000);

loadJobs();
