(function () {
  "use strict";
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  let reduce = preference.matches;
  let paused = reduce;
  const frames = new Set();
  let animationId;
  function animate() {
    animationId = null;
    if (paused || document.hidden) return;
    for (const draw of frames) draw();
    animationId = requestAnimationFrame(animate);
  }
  function queue(draw) {
    frames.add(draw);
  }
  function resume() {
    cancelAnimationFrame(animationId);
    document.body.classList.toggle("paused", paused);
    document
      .getElementById("motion")
      .setAttribute("aria-pressed", String(paused));
    document.getElementById("motion").textContent = paused
      ? "Продолжить анимацию"
      : "Приостановить анимацию";
    if (!paused && !document.hidden)
      animationId = requestAnimationFrame(animate);
  }
  document.getElementById("motion").addEventListener("click", () => {
    paused = !paused;
    resume();
  });
  document.addEventListener("visibilitychange", resume);
  preference.addEventListener("change", () => {
    reduce = preference.matches;
    paused = reduce;
    resume();
  });
  addEventListener("resize", () => {
    if (paused)
      requestAnimationFrame(() => {
        for (const draw of frames) draw();
      });
  });

  /* ---------- ambient canvas ---------- */
  var ac = document.getElementById("ambient"),
    ax = ac.getContext("2d");
  function sizeAmbient() {
    ac.width = innerWidth;
    ac.height = innerHeight;
  }
  sizeAmbient();
  addEventListener("resize", sizeAmbient);
  var t = 0;
  function ambient() {
    ax.clearRect(0, 0, ac.width, ac.height);
    var w = ac.width,
      h = ac.height;
    // faint dot grid drifting
    ax.fillStyle = "rgba(236,233,225,0.025)";
    var g = 46,
      ox = (t * 6) % g;
    for (var x = -g + ox; x < w; x += g) {
      for (var y = 0; y < h; y += g) {
        ax.fillRect(x, y, 1, 1);
      }
    }
    // slow baseline waveform near bottom
    ax.beginPath();
    ax.strokeStyle = "rgba(87,201,168,0.10)";
    ax.lineWidth = 1;
    var by = h * 0.86;
    for (var i = 0; i <= w; i += 6) {
      var v =
        Math.sin(i * 0.012 + t * 1.3) * 10 + Math.sin(i * 0.03 + t * 0.7) * 5;
      if (i === 0) ax.moveTo(i, by + v);
      else ax.lineTo(i, by + v);
    }
    ax.stroke();
    t += 0.012;
    queue(ambient);
  }
  ambient();

  /* ---------- hero RTA ---------- */
  var rta = document.getElementById("rta"),
    rx = rta.getContext("2d");
  var BARS = 31,
    vals = new Array(BARS),
    targets = new Array(BARS);
  // realistic-ish room curve: bass hump ~60-80Hz, mid dip, treble roll
  function roomTarget(i) {
    var f = 20 * Math.pow(1000, i / (BARS - 1)); // 20..20000
    var hump = 9 * Math.exp(-Math.pow((Math.log2(f) - 6.2) / 1.1, 2)); // ~75Hz room mode
    var dip = -5 * Math.exp(-Math.pow((Math.log2(f) - 8.5) / 1.4, 2)); // ~360Hz dip
    var roll = -Math.max(0, Math.log2(f) - 12) * 2.2; // treble roll
    return 60 + hump + dip + roll;
  }
  for (var i = 0; i < BARS; i++) {
    vals[i] = roomTarget(i);
    targets[i] = roomTarget(i);
  }
  function sizeRta() {
    var r = rta.getBoundingClientRect();
    rta.width = r.width * devicePixelRatio;
    rta.height = r.height * devicePixelRatio;
    rx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  }
  sizeRta();
  addEventListener("resize", sizeRta);
  function drawRta() {
    var w = rta.width / devicePixelRatio,
      h = rta.height / devicePixelRatio;
    rx.clearRect(0, 0, w, h);
    // gridlines
    rx.strokeStyle = "rgba(236,233,225,0.05)";
    rx.lineWidth = 1;
    for (var gy = 0; gy <= 4; gy++) {
      var yy = (h * gy) / 4;
      rx.beginPath();
      rx.moveTo(0, yy);
      rx.lineTo(w, yy);
      rx.stroke();
    }
    var bw = w / BARS,
      min = 30,
      max = 90;
    // bars
    for (var i = 0; i < BARS; i++) {
      if (Math.random() < 0.08)
        targets[i] = roomTarget(i) + (Math.random() - 0.5) * 4;
      vals[i] += (targets[i] - vals[i]) * 0.18;
      var n = (vals[i] - min) / (max - min);
      n = Math.max(0, Math.min(1, n));
      var bh = n * h,
        x = i * bw + bw * 0.18,
        bww = bw * 0.64;
      var hot = vals[i] > 66;
      rx.fillStyle = hot ? "rgba(224,145,63,0.55)" : "rgba(87,201,168,0.42)";
      rx.fillRect(x, h - bh, bww, bh);
      rx.fillStyle = hot ? "rgba(224,145,63,0.95)" : "rgba(87,201,168,0.95)";
      rx.fillRect(x, h - bh, bww, 2);
    }
    // smooth curve overlay
    rx.beginPath();
    rx.strokeStyle = "rgba(236,233,225,0.5)";
    rx.lineWidth = 1.4;
    for (var j = 0; j < BARS; j++) {
      var n2 = (vals[j] - min) / (max - min);
      n2 = Math.max(0, Math.min(1, n2));
      var px = j * bw + bw / 2,
        py = h - n2 * h;
      if (j === 0) rx.moveTo(px, py);
      else rx.lineTo(px, py);
    }
    rx.stroke();
    var avg =
      vals.reduce(function (a, b) {
        return a + b;
      }, 0) / BARS;
    document.getElementById("spl").textContent =
      avg.toFixed(1) + " dB · модель";
    queue(drawRta);
  }
  drawRta();

  /* ---------- mini FR in marker ---------- */
  function spark(canvasId, color, seed) {
    var c = document.getElementById(canvasId);
    if (!c) return;
    var x = c.getContext("2d");
    function fit() {
      var r = c.getBoundingClientRect();
      c.width = r.width * devicePixelRatio;
      c.height = r.height * devicePixelRatio;
      x.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    }
    fit();
    var ph = seed || 0;
    function d() {
      var w = c.width / devicePixelRatio,
        h = c.height / devicePixelRatio;
      x.clearRect(0, 0, w, h);
      x.beginPath();
      x.strokeStyle = color;
      x.lineWidth = 1.2;
      for (var i = 0; i <= w; i += 3) {
        var v =
          Math.sin(i * 0.18 + ph) * 0.25 + Math.sin(i * 0.05 + ph * 0.5) * 0.35;
        var y = h * 0.5 + v * h * 0.4;
        if (i === 0) x.moveTo(i, y);
        else x.lineTo(i, y);
      }
      x.stroke();
      ph += 0.05;
      queue(d);
    }
    d();
    addEventListener("resize", fit);
  }
  spark("miniFR", "#57c9a8", 0);

  /* ---------- hud live line ---------- */
  (function () {
    var c = document.getElementById("hudlive");
    if (!c) return;
    var x = c.getContext("2d"),
      ph = 2;
    function fit() {
      var r = c.getBoundingClientRect();
      c.width = r.width * devicePixelRatio;
      c.height = r.height * devicePixelRatio;
      x.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    }
    fit();
    addEventListener("resize", fit);
    function d() {
      var w = c.width / devicePixelRatio,
        h = c.height / devicePixelRatio;
      x.clearRect(0, 0, w, h);
      x.beginPath();
      x.strokeStyle = "#57c9a8";
      x.lineWidth = 1;
      for (var i = 0; i <= w; i += 2) {
        var v =
          Math.sin(i * 0.25 + ph) * 0.3 + Math.sin(i * 0.07 + ph * 1.7) * 0.3;
        var y = h / 2 + v * h * 0.4;
        if (i === 0) x.moveTo(i, y);
        else x.lineTo(i, y);
      }
      x.stroke();
      ph += 0.12;
      queue(d);
    }
    d();
  })();

  /* ---------- ticking 6DoF coords ---------- */
  var bx = 1.2,
    by2 = 0.4,
    bz = 1.18;
  setInterval(function () {
    if (paused || document.hidden) return;
    document.getElementById("cx").textContent = (
      bx +
      (Math.random() - 0.5) * 0.02
    ).toFixed(2);
    document.getElementById("cy").textContent = (
      by2 +
      (Math.random() - 0.5) * 0.02
    ).toFixed(2);
    document.getElementById("cz").textContent = (
      bz +
      (Math.random() - 0.5) * 0.01
    ).toFixed(2);
    document.getElementById("score").textContent = (
      0.82 +
      (Math.random() - 0.5) * 0.02
    ).toFixed(2);
  }, 420);

  /* ---------- AR layer switching ---------- */
  var ctrls = document.getElementById("ctrls"),
    ar = document.getElementById("ar");
  ctrls.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    var L = b.getAttribute("data-layer");
    [].forEach.call(ctrls.children, function (x) {
      x.classList.toggle("on", x === b);
      x.setAttribute("aria-pressed", String(x === b));
    });
    [].forEach.call(ar.querySelectorAll(".layer"), function (l) {
      l.classList.toggle("on", l.getAttribute("data-layer") === L);
      l.setAttribute("aria-hidden", String(l.getAttribute("data-layer") !== L));
    });
  });

  /* ---------- reveal on scroll ---------- */
  var io = new IntersectionObserver(
    function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      });
    },
    { threshold: 0.15 },
  );
  [].forEach.call(document.querySelectorAll(".reveal"), function (el) {
    io.observe(el);
  });

  /* ---------- timeline fill + dotnav spy ---------- */
  var tl = document.getElementById("tl"),
    fill = document.getElementById("tlfill");
  var sections = ["top", "timeline", "final", "hardware"].map(function (id) {
    return document.getElementById(id);
  });
  var dots = [].slice.call(document.querySelectorAll("#dotnav a"));
  function onScroll() {
    if (tl) {
      var r = tl.getBoundingClientRect(),
        vh = innerHeight;
      var total = r.height,
        passed = Math.min(Math.max(vh * 0.5 - r.top, 0), total);
      fill.style.height = (passed / total) * 100 + "%";
    }
    var cur = sections[0];
    sections.forEach(function (s) {
      if (s && s.getBoundingClientRect().top < innerHeight * 0.4) cur = s;
    });
    dots.forEach(function (d) {
      d.classList.toggle("on", d.getAttribute("data-s") === cur.id);
    });
  }
  var ticking = false;
  addEventListener("scroll", function () {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(function () {
        onScroll();
        ticking = false;
      });
    }
  });
  onScroll();
  resume();
})();
