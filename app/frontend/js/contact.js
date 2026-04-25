function getSession() {
  try {
    const raw = localStorage.getItem("ngoSession");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

const session = getSession();
if (session?.id) {
  const home = document.querySelector(".navbar nav a[href='index.html']");
  if (home) home.setAttribute("href", "ngo.html");

  const logo = document.querySelector(".navbar .logo");
  if (logo) {
    logo.addEventListener("click", () => {
      window.location.href = "ngo.html";
    });
  }
}

const yearEl = document.getElementById("year");
if (yearEl) yearEl.textContent = new Date().getFullYear();

const links = document.querySelectorAll(".navbar nav a[href]");
for (const a of links) {
  const href = (a.getAttribute("href") || "").toLowerCase();
  if (href.endsWith("contact.html")) a.classList.add("active");
}

const form = document.getElementById("contactForm");
const msg = document.getElementById("contactMessage");

if (form) {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (msg) msg.textContent = "Thanks! Your message has been received.";
    form.reset();
  });
}