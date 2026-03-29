/**
 * Mermaid Zoom Plugin for Zensical
 *
 * Adds a zoom button to every Mermaid diagram. Clicking it opens a
 * full-screen modal where the user can pan (drag) and zoom (scroll wheel
 * or toolbar buttons) the diagram.
 *
 * https://github.com/FedeArre/zensical-mermaid-zoom
 */
(function () {
  "use strict";

  // --- SVG icon markup ---
  var ICON_EXPAND =
    '<svg viewBox="0 0 24 24"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>';
  var ICON_ZOOM_IN =
    '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>';
  var ICON_ZOOM_OUT =
    '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>';
  var ICON_RESET =
    '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><polyline points="3 3 3 8 8 8"/></svg>';
  var ICON_CLOSE =
    '<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

  // --- Constants ---
  var MIN_SCALE = 0.2;
  var MAX_SCALE = 5;
  var ZOOM_STEP = 0.15;
  var zoomSeq = 0;

  // Mermaid source texts captured before Zensical renders them into shadow DOM
  var diagramSources = [];

  // --- Helpers ---
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "className") node.className = attrs[k];
        else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), attrs[k]);
        else node.setAttribute(k, attrs[k]);
      });
    }
    if (typeof children === "string") node.innerHTML = children;
    else if (Array.isArray(children)) children.forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  // Capture Mermaid source text from <pre> blocks, must run befroe Zensical processes them into closed shadow DOM.
  function captureSources() {
    var sources = [];
    document.querySelectorAll("pre.mermaid").forEach(function (pre) {
      var code = pre.querySelector("code");
      var text = (code ? code.textContent : pre.textContent).trim();
      sources.push(text);
    });

    // Only update if we found sources — Zensical removes the .mermaid class synchronously during component mounting, so a later call may find nothing. Keep the previous capture in that case.
    if (sources.length > 0) {
      diagramSources = sources;
    }
  }

  //  After Mermaid renders, attach zoom buttons to hosts
  function initMermaidZoom() {
    // Zensical replaces <pre class="mermaid"> with <div class="mermaid">
    var hosts = document.querySelectorAll("div.mermaid");
    hosts.forEach(function (host, index) {
      if (host.dataset.zoomAttached) return;
      host.dataset.zoomAttached = "true";

      var source = diagramSources[index];
      if (!source) return;

      // Wrap for positioning
      var wrapper = host.parentElement;
      if (!wrapper || !wrapper.classList.contains("mermaid-zoom-wrapper")) {
        wrapper = el("div", { className: "mermaid-zoom-wrapper" });
        host.parentNode.insertBefore(wrapper, host);
        wrapper.appendChild(host);
      }

      // Create zoom button
      var btn = el("button", {
        className: "mermaid-zoom-btn",
        title: "Open diagram in fullscreen",
        "aria-label": "Zoom into diagram",
        onclick: function () { openModal(source); }
      }, ICON_EXPAND);

      wrapper.appendChild(btn);
    });
  }

  // Re-render Mermaid source into the modal
  function openModal(sourceText) {
    if (typeof mermaid === "undefined") return;

    var id = "__mermaid_zoom_" + zoomSeq++;
    mermaid.render(id, sourceText).then(function (result) {
      var svgString = result.svg;
      var bindFn = result.fn;

      // Parse SVG string into a DOM element
      var tmp = document.createElement("div");
      tmp.innerHTML = svgString;
      var svgClone = tmp.querySelector("svg");
      if (!svgClone) return;

      // Clean up Mermaid's temp container if it lingers
      var temp = document.getElementById("d" + id);
      if (temp) temp.remove();

      // Read natural dimensions from the SVG
      var vb = svgClone.getAttribute("viewBox");
      var natW, natH;
      if (vb) {
        var parts = vb.split(/[\s,]+/);
        natW = parseFloat(parts[2]) || parseFloat(svgClone.getAttribute("width")) || 800;
        natH = parseFloat(parts[3]) || parseFloat(svgClone.getAttribute("height")) || 600;
      } else {
        natW = parseFloat(svgClone.getAttribute("width")) || 800;
        natH = parseFloat(svgClone.getAttribute("height")) || 600;
      }

      // Set explicit dimensions; CSS transform handles zoom/pan
      svgClone.setAttribute("width", natW);
      svgClone.setAttribute("height", natH);
      svgClone.style.maxWidth = "none";
      svgClone.style.overflow = "visible";

      showZoomModal(svgClone, natW, natH);

      // Bind Mermaid interactive handlers if any
      if (bindFn) {
        try { bindFn(svgClone.parentElement); } catch (_) { /* ignore */ }
      }
    }).catch(function (err) {
      console.error("Mermaid zoom: render failed", err);
    });
  }

  // Build and show the zoom modal
  function showZoomModal(svgClone, natW, natH) {
    var scale = 1, panX = 0, panY = 0;
    var dragging = false, startX, startY;

    var zoomLabel = el("span", { className: "mermaid-zoom-level" }, "100%");
    var content = el("div", { className: "mermaid-zoom-content" }, [svgClone]);
    var viewport = el("div", { className: "mermaid-zoom-viewport" }, [content]);

    var toolbar = el("div", { className: "mermaid-zoom-toolbar" }, [
      el("button", { title: "Zoom in", "aria-label": "Zoom in", onclick: function () { zoom(ZOOM_STEP); } }, ICON_ZOOM_IN),
      el("button", { title: "Zoom out", "aria-label": "Zoom out", onclick: function () { zoom(-ZOOM_STEP); } }, ICON_ZOOM_OUT),
      zoomLabel,
      el("button", { title: "Reset view", "aria-label": "Reset view", onclick: resetView }, ICON_RESET),
      el("button", { title: "Close", "aria-label": "Close", onclick: close }, ICON_CLOSE)
    ]);

    var modal = el("div", { className: "mermaid-zoom-modal" }, [toolbar, viewport]);
    var overlay = el("div", { className: "mermaid-zoom-overlay" }, [modal]);

    document.body.appendChild(overlay);
    overlay.offsetWidth; // reflow
    overlay.classList.add("active");

    // Delay resetView so the viewport has its final layout dimensions
    setTimeout(function () { resetView(); }, 50);

    function applyTransform() {
      content.style.transform = "translate(" + panX + "px, " + panY + "px) scale(" + scale + ")";
      zoomLabel.textContent = Math.round(scale * 100) + "%";
    }

    function zoom(delta, cx, cy) {
      var prev = scale;
      scale = clamp(scale + delta * scale, MIN_SCALE, MAX_SCALE);
      var ratio = scale / prev;
      if (cx === undefined) {
        cx = viewport.clientWidth / 2;
        cy = viewport.clientHeight / 2;
      }
      panX = cx - ratio * (cx - panX);
      panY = cy - ratio * (cy - panY);
      applyTransform();
    }

    function resetView() {
      scale = 1;
      var vw = viewport.clientWidth;
      var vh = viewport.clientHeight;
      if (natW && natH) {
        scale = Math.min(vw / natW, vh / natH, 1) * 0.9;
      }
      panX = (vw - natW * scale) / 2;
      panY = (vh - natH * scale) / 2;
      applyTransform();
    }

    function close() {
      overlay.classList.remove("active");
      setTimeout(function () { overlay.remove(); }, 200);
      document.removeEventListener("keydown", onKey);
    }

    // Wheel zoom
    viewport.addEventListener("wheel", function (e) {
      e.preventDefault();
      var rect = viewport.getBoundingClientRect();
      zoom(e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP, e.clientX - rect.left, e.clientY - rect.top);
    }, { passive: false });

    // Mouse drag pan
    viewport.addEventListener("mousedown", function (e) {
      if (e.button !== 0) return;
      dragging = true;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
    });
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    function onMouseMove(e) {
      if (!dragging) return;
      panX = e.clientX - startX;
      panY = e.clientY - startY;
      applyTransform();
    }
    function onMouseUp() { dragging = false; }

    // Touch pan & pinch zoom
    var lastTouchDist = null;
    viewport.addEventListener("touchstart", function (e) {
      if (e.touches.length === 1) {
        dragging = true;
        startX = e.touches[0].clientX - panX;
        startY = e.touches[0].clientY - panY;
      } else if (e.touches.length === 2) {
        dragging = false;
        lastTouchDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
      }
    }, { passive: true });

    viewport.addEventListener("touchmove", function (e) {
      e.preventDefault();
      if (e.touches.length === 1 && dragging) {
        panX = e.touches[0].clientX - startX;
        panY = e.touches[0].clientY - startY;
        applyTransform();
      } else if (e.touches.length === 2 && lastTouchDist !== null) {
        var dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        var rect = viewport.getBoundingClientRect();
        var cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
        var cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
        zoom((dist - lastTouchDist) * 0.005, cx, cy);
        lastTouchDist = dist;
      }
    }, { passive: false });

    viewport.addEventListener("touchend", function () {
      dragging = false;
      lastTouchDist = null;
    }, { passive: true });

    // Close on overlay click or Escape
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) close();
    });
    document.addEventListener("keydown", onKey);
    function onKey(e) { if (e.key === "Escape") close(); }

    // Cleanup global listeners when overlay is removed
    var observer = new MutationObserver(function () {
      if (!document.body.contains(overlay)) {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
        observer.disconnect();
      }
    });
    observer.observe(document.body, { childList: true });
  }

  // Capture sources immediately at script load (before Mermaid processes them)
  captureSources();

  if (typeof document$ !== "undefined") {
    document$.subscribe(function () {
      // Re-capture for instant navigation (new page content loaded)
      captureSources();
      // Wait for Mermaid to finish rendering into shadow DOM
      setTimeout(initMermaidZoom, 1000);
    });
  } else {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () {
        captureSources();
        setTimeout(initMermaidZoom, 1000);
      });
    } else {
      setTimeout(initMermaidZoom, 1000);
    }
  }
})();
