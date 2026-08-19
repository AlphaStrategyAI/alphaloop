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
    button.textContent = job.run_id + " — " + job.research_outcome;
    button.addEventListener("click", function () {
      showJob(job.run_id);
    });
    item.appendChild(button);
    list.appendChild(item);
  }
}

loadJobs();
