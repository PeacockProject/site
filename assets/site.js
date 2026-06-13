/* site.js — PeacockProject landing (light-academia, builder design language).
 * Vanilla, no build step. Inlines the peacock marks (so they take the
 * iridescent gradient fill), runs the intro reveal, scroll reveals, header
 * state, and the signal visualizer. */
(function () {
  "use strict";

  var reduce = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- inline the peacock SVG marks so CSS url(#irid) can fill them ---- */
  var MARK = {
    head: "/assets/peacock-head.svg",
    full: "/assets/peacock-full.svg",
  };
  var cache = {};
  function inlineMarks() {
    var nodes = document.querySelectorAll("[data-mark]");
    nodes.forEach(function (el) {
      var key = el.getAttribute("data-mark");
      var url = MARK[key];
      if (!url) return;
      if (cache[key]) { el.innerHTML = cache[key]; return; }
      fetch(url)
        .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
        .then(function (txt) {
          // strip any hard-coded fills so CSS controls color
          txt = txt.replace(/fill:#[0-9a-fA-F]{3,8}/g, "fill:currentColor");
          cache[key] = txt;
          el.innerHTML = txt;
        })
        .catch(function () { /* mark just stays empty; layout unaffected */ });
    });
  }

  /* ---- intro reveal — "Yours / Only" mask (once ever, via localStorage) ---- */
  function runIntro() {
    var intro = document.getElementById("intro");
    if (!intro) return;
    var seen;
    try { seen = window.localStorage.getItem("peacock_intro_seen"); } catch (e) { seen = null; }
    if (reduce || seen) {
      intro.classList.add("done");
      return;
    }
    document.body.style.overflow = "hidden";
    window.setTimeout(function () {
      intro.classList.add("done");
      document.body.style.overflow = "";
      try { window.localStorage.setItem("peacock_intro_seen", "true"); } catch (e) {}
      // let the reveal system recompute now that the page is interactive
      window.dispatchEvent(new Event("peacock:refresh-reveals"));
    }, 2100);
  }

  /* ---- scroll reveals — the original "reveal-jump": add .in when in view,
   * REMOVE it when scrolled well past, so sections re-animate on re-entry. ---- */
  function runReveals() {
    var els = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
    if (reduce) {
      els.forEach(function (el) { el.classList.add("in"); });
      return;
    }
    var ticking = false;
    function check() {
      ticking = false;
      var h = window.innerHeight, top = h - 24;
      els.forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (!el.classList.contains("in")) {
          if (r.top <= top && r.bottom >= 24) el.classList.add("in");
        } else if (r.bottom < -72 || r.top > h + 72) {
          el.classList.remove("in");
        }
      });
    }
    function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(check); } }
    check();
    requestAnimationFrame(onScroll);
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    window.addEventListener("peacock:refresh-reveals", onScroll);
  }

  /* ---- header: solidify slightly once scrolled ---- */
  function runHeader() {
    var hdr = document.querySelector(".hdr");
    if (!hdr) return;
    var onScroll = function () {
      if (window.scrollY > 12) {
        hdr.style.background = "rgba(243,243,241,.9)";
        hdr.style.borderColor = "rgba(32,31,36,.16)";
      } else {
        hdr.style.background = "";
        hdr.style.borderColor = "";
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---- signal visualizer — the original SignalVisualizer algorithm.
   * A calm idle wave that always breathes, punctuated every 4–8s by an energy
   * burst (decaying impulse) that spikes the bars with a center-weighted
   * envelope, accelerates the phase, and physically trembles the whole panel.
   * Ported verbatim from the original; only the bar gradient is re-themed. */
  function runVisualizer() {
    var host = document.getElementById("visualizer");
    if (!host) return;
    var reactor = host.closest(".signal-container") || host;
    var N = 32, bars = [];
    for (var k = 0; k < N; k++) {
      var b = document.createElement("div");
      b.className = "vis-bar";
      host.appendChild(b);
      bars.push(b);
    }

    if (reduce) {
      bars.forEach(function (bar, e) {
        var h = Math.max(5, Math.min(100, 35 + 30 * Math.sin(-0.2 * e) + 15 * Math.cos(-0.15 * e)));
        bar.style.height = h + "%";
      });
      return;
    }

    var a = 0, i = 0, r = 0, n = 4000, raf = 0, running = true;
    function frame(l) {
      // fire a new energy burst on its randomized interval
      if (l - r > n) { r = l; n = 4000 + 4000 * Math.random(); i = 4; }
      var c = 0.05 + 0.04 * (i *= 0.94);   // phase advances faster while energized
      a += c;
      for (var e = 0; e < N; e++) {
        var bar = bars[e];
        // calm idle wave — two slow traveling waves around a ~35% baseline
        var h = 35 + 30 * Math.sin(a - 0.2 * e) + 15 * Math.cos(0.7 * a - 0.15 * e);
        // burst layer: center-weighted spike that decays with the impulse
        if (i > 0.05) {
          h += (0.7 * (0.5 * Math.sin(0.3 * e + 0.003 * l) + 0.5)
              + 0.3 * (0.5 * Math.cos(0.8 * e - 0.007 * l) + 0.5))
              * i * 20 * Math.sin(e / 32 * Math.PI);
        }
        h = Math.max(5, Math.min(100, h));
        bar.style.height = h + "%";
      }
      // the whole panel trembles with the remaining energy, then settles
      if (reactor) {
        var tx = Math.sin(0.005 * l) * i * 1.5;
        var ty = Math.cos(0.003 * l) * i * 2;
        var rz = Math.sin(0.002 * l) * i * 0.2;
        reactor.style.transform = "translate3d(" + tx.toFixed(2) + "px," + ty.toFixed(2) + "px,0) rotateZ(" + rz.toFixed(2) + "deg)";
      }
      if (running) raf = window.requestAnimationFrame(frame);
    }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) {
        var on = es[0].isIntersecting;
        if (on && !running) { running = true; raf = window.requestAnimationFrame(frame); }
        running = on;
      }, { threshold: 0.02 }).observe(host);
    }
    raf = window.requestAnimationFrame(frame);
  }

  /* ---- footer brand roller — original SiteFooter cadence: "PeacockProject"
   * dwells ~6.2s, "Yours Only" flashes ~1.2s; data-state/-direction drive the
   * CSS slam/kick/flicker. ---- */
  function runFooterRoller() {
    var el = document.getElementById("brandRoller");
    if (!el) return;
    if (reduce) { el.setAttribute("data-state", "project"); return; }
    var state = "project";
    (function loop() {
      var dwell = state === "alt" ? 1200 : 6200;   // dwell on the CURRENT state
      window.setTimeout(function () {
        el.setAttribute("data-direction", state === "project" ? "to-alt" : "to-project");
        state = state === "project" ? "alt" : "project";
        el.setAttribute("data-state", state);
        loop();
      }, dwell);
    })();
  }

  function init() {
    inlineMarks();
    runIntro();
    runReveals();
    runHeader();
    runVisualizer();
    runFooterRoller();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
