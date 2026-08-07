/* ============================================
   SG ATLAS — Protein Animation Scroller
   ============================================

   HOW TO ADD YOUR ANIMATIONS:
   Just add entries to the PROTEIN_ANIMATIONS array below.
   Each entry needs:
     - src:     path to your file, e.g. "assets/tau-fold.mp4" or "assets/asyn-fibril.gif"
     - type:    "video" or "image" (gifs count as "image")
     - label:   short caption shown under the animation
     - pdbId:   optional PDB ID shown next to the label (leave "" to omit)

   Videos autoplay muted + loop automatically. Just drop files into /assets
   and reference them here — no other code changes needed.
*/

const PROTEIN_ANIMATIONS = [
  // Example entries — replace with your real files once you have them.
  // { src: "assets/tau-fibril.mp4", type: "video", label: "Tau fibril, cross-beta core", pdbId: "6QJH" },
  // { src: "assets/asyn-rod.gif",   type: "image", label: "Alpha-synuclein rod polymorph", pdbId: "6CU7" },
];

(function initScroller() {
  const track = document.getElementById("scrollerTrack");
  const dotsWrap = document.getElementById("scrollerDots");
  const leftArrow = document.querySelector(".scroller-arrow-left");
  const rightArrow = document.querySelector(".scroller-arrow-right");

  if (!track) return;

  // Empty state — shown until animations are supplied
  if (!PROTEIN_ANIMATIONS.length) {
    track.innerHTML = `
      <div class="scroller-empty">
        Protein animations will appear here.<br>
        Add entries to <code>PROTEIN_ANIMATIONS</code> in script.js.
      </div>`;
    if (leftArrow) leftArrow.disabled = true;
    if (rightArrow) rightArrow.disabled = true;
    return;
  }

  // Build slides
  PROTEIN_ANIMATIONS.forEach((item) => {
    const slide = document.createElement("div");
    slide.className = "scroller-slide";

    const media = document.createElement("div");
    media.className = "scroller-slide-media";

    if (item.type === "video") {
      const video = document.createElement("video");
      video.src = item.src;
      video.autoplay = true;
      video.muted = true;
      video.loop = true;
      video.playsInline = true;
      media.appendChild(video);
    } else {
      const img = document.createElement("img");
      img.src = item.src;
      img.alt = item.label || "Protein structure animation";
      media.appendChild(img);
    }

    const caption = document.createElement("div");
    caption.className = "scroller-slide-caption";
    caption.innerHTML = `
      <span class="label">${item.label || ""}</span>
      ${item.pdbId ? `<span class="pdb-id">${item.pdbId}</span>` : ""}
    `;

    slide.appendChild(media);
    slide.appendChild(caption);
    track.appendChild(slide);
  });

  // Build dots
  const dots = [];
  PROTEIN_ANIMATIONS.forEach((_, i) => {
    const dot = document.createElement("button");
    dot.className = "scroller-dot" + (i === 0 ? " active" : "");
    dot.setAttribute("aria-label", `Go to slide ${i + 1}`);
    dot.addEventListener("click", () => scrollToSlide(i));
    dotsWrap.appendChild(dot);
    dots.push(dot);
  });

  function scrollToSlide(index) {
    const slide = track.children[index];
    if (!slide) return;
    track.scrollTo({
      left: slide.offsetLeft - track.offsetLeft,
      behavior: "smooth",
    });
  }

  function currentIndex() {
    const scrollLeft = track.scrollLeft;
    let closest = 0;
    let closestDist = Infinity;
    Array.from(track.children).forEach((slide, i) => {
      const dist = Math.abs(slide.offsetLeft - track.offsetLeft - scrollLeft);
      if (dist < closestDist) {
        closestDist = dist;
        closest = i;
      }
    });
    return closest;
  }

  function updateDots() {
    const idx = currentIndex();
    dots.forEach((d, i) => d.classList.toggle("active", i === idx));
    if (leftArrow) leftArrow.disabled = idx === 0;
    if (rightArrow) rightArrow.disabled = idx === PROTEIN_ANIMATIONS.length - 1;
  }

  let scrollTimeout;
  track.addEventListener("scroll", () => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateDots, 80);
  });

  if (leftArrow) {
    leftArrow.addEventListener("click", () => {
      scrollToSlide(Math.max(0, currentIndex() - 1));
    });
  }
  if (rightArrow) {
    rightArrow.addEventListener("click", () => {
      scrollToSlide(Math.min(PROTEIN_ANIMATIONS.length - 1, currentIndex() + 1));
    });
  }

  updateDots();
})();
