function getNgoSession() {
  try {
    const raw = localStorage.getItem("ngoSession");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function getChatSessionId() {
  return (localStorage.getItem("chatSessionId") || "").trim() || null;
}

function setChatSessionId(sessionId) {
  if (!sessionId) return;
  localStorage.setItem("chatSessionId", sessionId);
}

const API_BASE_URL = "http://localhost:8000";

function makeApiUrl() {
  return `${API_BASE_URL}/api/chat`;
}

const ngoSession = getNgoSession();
if (ngoSession?.id) {
  const home = document.querySelector(".navbar nav a[href='index.html']");
  if (home) home.setAttribute("href", "ngo.html");

  const back = document.querySelector(".navbar a.btn-outline[href='index.html']");
  if (back) back.setAttribute("href", "ngo.html");

  const logo = document.querySelector(".navbar .logo");
  if (logo) {
    logo.addEventListener("click", () => {
      window.location.href = "ngo.html";
    });
  }
}

const chatWindow = document.getElementById("chatWindow");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const clearChatBtn = document.getElementById("clearChatBtn");
const chatError = document.getElementById("chatError");
const chatErrorText = document.getElementById("chatErrorText");
const retryBtn = document.getElementById("retryBtn");

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

function showError(message) {
  if (!chatError || !chatErrorText) return;
  chatErrorText.textContent = message;
  chatError.hidden = false;
}

function hideError() {
  if (!chatError || !chatErrorText) return;
  chatErrorText.textContent = "";
  chatError.hidden = true;
}

function resetChat() {
  localStorage.removeItem("chatSessionId");
  localStorage.removeItem("lastMatchedNgos");
  hideError();
  chatWindow.innerHTML = "";
  addMessage("Hi! Tell me about your donation (food type, quantity, pickup time, and location).", "bot");
}

function typeOut(el, text) {
  const full = String(text ?? "");
  el.textContent = "";

  let i = 0;
  return new Promise((resolve) => {
    const tick = () => {
      if (i >= full.length) {
        resolve();
        return;
      }

      const step = 1 + Math.floor(Math.random() * 3);
      i = Math.min(full.length, i + step);
      el.textContent = full.slice(0, i);
      chatWindow.scrollTop = chatWindow.scrollHeight;

      setTimeout(tick, 30);
    };

    tick();
  });
}

async function sendChat(userText) {
  const res = await fetch(makeApiUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message: userText,
      session_id: getChatSessionId()
    })
  });

  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }

  const data = await res.json();

  if (data?.session_id) {
    setChatSessionId(data.session_id);
  }

  if (data?.matched_ngos) {
    localStorage.setItem("lastMatchedNgos", JSON.stringify(data.matched_ngos));
  }

  return data;
}

clearChatBtn.addEventListener("click", resetChat);

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideError();

  const text = (chatInput.value || "").trim();
  if (!text) return;

  addMessage(text, "user");
  chatInput.value = "";

  const botEl = addMessage("", "bot");

  chatInput.disabled = true;

  try {
    const data = await sendChat(text);

    console.log(data);

    if (!data || typeof data !== "object") {
      botEl.remove();
      showError("Server is not responding. Please retry again in a few minutes.");
      return;
    }

    if (data.status === "error") {
      botEl.remove();
      showError("Server is not responding. Please retry again in a few minutes.");
      return;
    }

    const msg = (data.message || "").trim() || "(No response)";
    await typeOut(botEl, msg);
  } catch (err) {
    botEl.remove();
    showError("Server is not responding. Please retry again in a few minutes.");
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
  }
});

if (retryBtn) {
  retryBtn.addEventListener("click", () => {
    resetChat();
    chatInput.focus();
  });
}

resetChat();