const statusNode = document.querySelector("#status");
const labsNode = document.querySelector("#labs");

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function renderLab(lab) {
  const card = el("article", "card");
  const meta = el("div", "meta");
  meta.append(
    el("span", "tag", `Week ${String(lab.week).padStart(2, "0")}`),
    el("span", `tag ${lab.status === "implemented" ? "ready" : ""}`, lab.status),
    el("span", "tag", lab.difficulty),
    el("span", "tag", `${lab.duration_minutes} min`),
  );
  card.append(el("h3", "", lab.title), meta, el("p", "", lab.summary));

  if (lab.services.length > 0) {
    const list = el("ul");
    for (const service of lab.services) {
      list.append(el("li", "", `${service.name}: ${service.protocol}/${service.port}`));
    }
    card.append(list);
  }
  return card;
}

async function load() {
  try {
    const health = await fetch("/api/health").then((response) => response.json());
    statusNode.textContent = `Lab manager ${health.version} online. Actions ${health.actions_enabled ? "enabled" : "disabled"}.`;
    const payload = await fetch("/api/labs").then((response) => response.json());
    labsNode.replaceChildren(...payload.labs.map(renderLab));
  } catch (error) {
    statusNode.textContent = "Lab manager is unavailable. Start the service on 127.0.0.1:8080.";
    statusNode.classList.add("error");
    console.error(error);
  }
}

load();
