const CREDENTIALS = {
  "info@jayden.com": { id: "NGO_001", name: "Jayden BKT Kitchen", password: "rescue001" },
  "info@lostfoodproject.org": { id: "NGO_002", name: "The Lost Food Project", password: "rescue002" },
  "admin@foodaidfoundation.com": { id: "NGO_003", name: "Food Aid Foundation", password: "rescue003" },
  "yatim@orphancare.my": { id: "NGO_004", name: "Pertubuhan Kebajikan Anak-Anak Yatim", password: "rescue004" },
  "admin@rumahcharis.org": { id: "NGO_005", name: "Rumah Charis", password: "rescue005" },
  "food@mercy.org.my": { id: "NGO_006", name: "MERCY Malaysia", password: "rescue006" }
};

function normEmail(value) {
  return (value || "").trim().toLowerCase();
}

function getSession() {
  try {
    const raw = localStorage.getItem("ngoSession");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function setMessage(text, type) {
  let el = document.getElementById("loginMessage");
  if (!el) {
    el = document.createElement("div");
    el.id = "loginMessage";
    el.className = "login-message";
    const form = document.querySelector(".login-form");
    if (form) form.appendChild(el);
  }

  el.classList.remove("ok", "err");
  el.classList.add(type === "ok" ? "ok" : "err");
  el.textContent = text;
}

const existing = getSession();
if (existing?.id) {
  window.location.href = "ngo.html";
}

const form = document.querySelector(".login-form");

if (form) {
  form.addEventListener("submit", (e) => {
    e.preventDefault();

    const email = normEmail(form.querySelector("input[name='email']")?.value);
    const password = (form.querySelector("input[name='password']")?.value || "").trim();

    const record = CREDENTIALS[email];

    if (!record || record.password !== password) {
      setMessage("Invalid email or password.", "err");
      return;
    }

    const session = {
      id: record.id,
      name: record.name,
      email,
      loggedInAt: new Date().toISOString()
    };

    localStorage.setItem("ngoSession", JSON.stringify(session));
    setMessage(`Logged in as ${record.name} (${record.id}).`, "ok");
    window.location.href = "ngo.html";
  });
}