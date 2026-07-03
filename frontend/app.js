// Minimal chat-style frontend for the AI Data Analyst Agent API.
// No build step -- open this file directly or serve it with
// `python -m http.server` from the frontend/ directory.

// Adjust this if the API is running on a different host/port.
const API_BASE_URL = "http://127.0.0.1:8010";

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("ask-form");
const inputEl = document.getElementById("question-input");
const buttonEl = document.getElementById("ask-button");

function addUserBubble(text) {
  const bubble = document.createElement("div");
  bubble.className = "bubble user";
  bubble.textContent = text;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addLoadingBubble() {
  const bubble = document.createElement("div");
  bubble.className = "bubble agent loading";
  bubble.textContent = "Thinking...";
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function addErrorBubble(message) {
  const bubble = document.createElement("div");
  bubble.className = "bubble error";
  bubble.textContent = message;
  chatEl.appendChild(bubble);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function renderAgentResponse(bubble, data) {
  bubble.classList.remove("loading");
  bubble.innerHTML = "";

  const insightP = document.createElement("div");
  insightP.textContent = data.insight;
  bubble.appendChild(insightP);

  if (data.suggested_action) {
    const actionDiv = document.createElement("div");
    actionDiv.className = "action-line";
    actionDiv.textContent = "Suggested action: " + data.suggested_action;
    bubble.appendChild(actionDiv);
  }

  if (data.chart_url) {
    const chartLabel = document.createElement("div");
    chartLabel.className = "section-label";
    chartLabel.textContent = "Chart";
    bubble.appendChild(chartLabel);

    const img = document.createElement("img");
    img.className = "chart";
    img.src = API_BASE_URL + data.chart_url;
    img.alt = "Generated chart";
    bubble.appendChild(img);
  }

  const sqlLabel = document.createElement("div");
  sqlLabel.className = "section-label";
  sqlLabel.textContent = "Generated SQL";
  bubble.appendChild(sqlLabel);

  const sqlBlock = document.createElement("div");
  sqlBlock.className = "sql-block";
  sqlBlock.textContent = data.sql;
  bubble.appendChild(sqlBlock);

  chatEl.scrollTop = chatEl.scrollHeight;
}

async function askQuestion(question) {
  addUserBubble(question);
  const loadingBubble = addLoadingBubble();
  buttonEl.disabled = true;

  try {
    const response = await fetch(`${API_BASE_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();

    if (!response.ok) {
      loadingBubble.remove();
      addErrorBubble(data.detail || "Something went wrong.");
      return;
    }

    renderAgentResponse(loadingBubble, data);
  } catch (err) {
    loadingBubble.remove();
    addErrorBubble("Could not reach the API. Is it running at " + API_BASE_URL + "?");
  } finally {
    buttonEl.disabled = false;
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = inputEl.value.trim();
  if (!question) return;
  inputEl.value = "";
  askQuestion(question);
});

document.querySelectorAll(".example-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const question = chip.getAttribute("data-question");
    askQuestion(question);
  });
});
