// src/webui/static/app.js
const log = document.getElementById("log");
const approval = document.getElementById("approval");
const es = new EventSource("/events");
es.onmessage = (e) => { log.textContent += e.data + "\n"; };

async function pollApproval() {
  const r = await fetch("/pending");
  const d = await r.json();
  if (d.pending) {
    approval.hidden = false;
    document.getElementById("approval-text").textContent =
      JSON.stringify(d.action);
  } else {
    approval.hidden = true;
  }
}
document.getElementById("approve-btn").onclick = () => postApproval(true);
document.getElementById("reject-btn").onclick = () => postApproval(false);
async function postApproval(v) {
  await fetch("/approve", {method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({approve: v})});
  approval.hidden = true;
}
setInterval(pollApproval, 1000);
