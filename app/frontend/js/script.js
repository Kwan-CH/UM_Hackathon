let count = 47;

setInterval(() => {
    count++;
    document.getElementById("pickupCount").innerText = count + " Pickups";
}, 5000);