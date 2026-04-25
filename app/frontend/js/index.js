let count = 47;

setInterval(() => {
  count++;
  const el = document.getElementById("pickupCount");
  if (!el) return;
  el.innerText = count + " Pickups";
}, 5000);