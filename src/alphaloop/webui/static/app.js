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

async function showJob(runId) {
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
  const results = (job.evidence && job.evidence.results) || [];
  fillList(document.getElementById("evidence"), results, function (row) {
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
    button.addEventListener("click", function () {
      showJob(job.run_id);
    });
    item.appendChild(button);
    list.appendChild(item);
  }
}

async function submitJob() {
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

document.getElementById("submit-job").addEventListener("click", function () {
  submitJob();
});

setInterval(loadJobs, 2000);

loadJobs();
