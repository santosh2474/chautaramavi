/**
 * ==========================================================================
 * Shree Chautara Secondary School - Banner / Popup Media Viewer
 * Website: www.chautaramavi.edu.np
 * Vanilla JavaScript Component (No dependencies required)
 * ==========================================================================
 */

(function () {
    "use strict";

    class ScsBannerViewer {
        constructor() {
            // Configuration & media
            this.mediaList = (typeof bannerMedia !== "undefined" && Array.isArray(bannerMedia)) ? [...bannerMedia] : [];
            this.meta = (typeof bannerMeta !== "undefined" && typeof bannerMeta === "object") ? bannerMeta : {};
            this.settings = Object.assign({
                enabled: true,
                autoOpen: true,
                slideshow: false,
                slideshowInterval: 5000,
                rememberClosed: false,
                autoDetectPhp: true
            }, (typeof bannerSettings !== "undefined" ? bannerSettings : {}));

            this.currentIndex = 0;
            this.isOpen = false;
            this.slideshowTimer = null;
            this.activeVideo = null;

            // Image Zoom, Pan & Rotation state
            this.zoomScale = 1;
            this.minScale = 0.6;
            this.maxScale = 4.0;
            this.panX = 0;
            this.panY = 0;
            this.rotation = 0;
            this.isDragging = false;
            this.dragStartX = 0;
            this.dragStartY = 0;
            this.hasMovedDrag = false;

            // Touch pinch zoom state
            this.initialPinchDistance = null;
            this.initialPinchScale = 1;

            // DOM elements
            this.overlay = null;
            this.modal = null;
            this.bodyArea = null;
            this.mediaContainer = null;
            this.titleEl = null;
            this.counterEl = null;
            this.dotsContainer = null;
            this.zoomToolbar = null;
            this.zoomLevelEl = null;
            this.rotateBtn = null;
            this.openNewTabBtn = null;
            this.floatingTrigger = null;
            this.floatingCountEl = null;
            this.prevBtn = null;
            this.nextBtn = null;
            this.closeBtn = null;
            this.dontShowCheckbox = null;
            this.loaderEl = null;
            this.footerCaptionEl = null;

            // New-items tracking (items added to mediaList after user last dismissed)
            this.newItemsSinceDismissal = [];

            this.init();
        }

        async init() {
            // If the entire banner media viewer is disabled, do not initialize anything
            if (this.settings.enabled === false) {
                const existingTrigger = document.getElementById("scsFloatingTrigger");
                if (existingTrigger) existingTrigger.style.display = "none";
                const existingOverlay = document.getElementById("scsBannerOverlay");
                if (existingOverlay) existingOverlay.style.display = "none";
                console.log("[ScsBanner] Banner media viewer is disabled in bannerSettings.");
                return;
            }

            // Check PHP auto-detection only if enabled and running on http/https web server
            // (Browsers block fetch on file:// protocol with CORS error)
            const isWebProtocol = window.location.protocol === "http:" || window.location.protocol === "https:";
            if (this.settings.autoDetectPhp && isWebProtocol) {
                try {
                    const response = await fetch("banner/get_banners.php", { method: "GET", cache: "no-cache" });
                    if (response.ok) {
                        const dynamicList = await response.json();
                        if (Array.isArray(dynamicList) && dynamicList.length > 0) {
                            this.mediaList = dynamicList;
                        }
                    }
                } catch (e) {
                    // Fallback to bannerMedia silently
                }
            }

            if (!this.mediaList || this.mediaList.length === 0) {
                console.warn("[ScsBanner] No media items found in bannerMedia list.");
                return;
            }

            this.buildDOM();
            this.bindEvents();

            // Detect any new items added since user's last dismissal
            this.newItemsSinceDismissal = this.getNewItemsSinceDismissal();

            // Auto-open handling:
            // If new items have been added since the user's last "Don't show again" dismissal,
            // we override the suppression and re-open the viewer to show those new items.
            const dismissed = this.isDismissedWithoutNewItems();
            if (this.settings.autoOpen && !dismissed) {
                setTimeout(() => {
                    this.open(this.newItemsSinceDismissal.length > 0 ? this.getFirstNewItemIndex() : 0);
                }, 400);
            }

            // Visually signal new/updated items on the floating trigger
            this.updateFloatingTriggerNewBadge();
        }

        /**
         * Compute a fingerprint of the current media list.
         * Stored as a JSON array of sorted file paths.
         */
        getMediaFingerprint() {
            return JSON.stringify([...this.mediaList].sort());
        }

        /**
         * Returns the indices of items that were NOT present in the media list
         * at the time the user last clicked "Don't show again today".
         */
        getNewItemsSinceDismissal() {
            try {
                const storedFingerprint = localStorage.getItem("scs_banner_dismissed_fingerprint");
                if (!storedFingerprint) return [];
                const dismissedList = JSON.parse(storedFingerprint);
                if (!Array.isArray(dismissedList)) return [];
                const dismissedSet = new Set(dismissedList);
                return this.mediaList
                    .map((url, idx) => ({ url, idx }))
                    .filter(({ url }) => !dismissedSet.has(url));
            } catch (e) {
                return [];
            }
        }

        /**
         * Returns the index of the first new item, or 0 if none found.
         */
        getFirstNewItemIndex() {
            if (this.newItemsSinceDismissal.length > 0) {
                return this.newItemsSinceDismissal[0].idx;
            }
            return 0;
        }

        /**
         * isDismissedWithoutNewItems returns true ONLY if:
         * - User clicked "Don't show again today" within the last 24 hours, AND
         * - No new items have been added to the media list since that dismissal.
         * If new items were added, we always return false (show the viewer).
         */
        isDismissedWithoutNewItems() {
            try {
                const dismissedTime = localStorage.getItem("scs_banner_closed_timestamp");
                if (!dismissedTime) return false;

                const oneDayMs = 24 * 60 * 60 * 1000;
                const now = Date.now();
                const withinDay = (now - parseInt(dismissedTime, 10)) < oneDayMs;

                if (!withinDay) return false;

                // Even within 24 hours: if new items were added, show anyway
                if (this.newItemsSinceDismissal.length > 0) {
                    return false;
                }

                return true;
            } catch (e) {
                return false;
            }
        }

        /**
         * Legacy helper kept for compatibility.
         */
        isDismissed() {
            return this.isDismissedWithoutNewItems();
        }

        dismiss() {
            try {
                localStorage.setItem("scs_banner_closed_timestamp", Date.now().toString());
                // Store fingerprint of current media list so we can detect new additions later
                localStorage.setItem("scs_banner_dismissed_fingerprint", this.getMediaFingerprint());
                // Reset new-items tracking so the trigger badge clears
                this.newItemsSinceDismissal = [];
                this.updateFloatingTriggerNewBadge();
            } catch (e) {}
        }

        clearDismiss() {
            try {
                localStorage.removeItem("scs_banner_closed_timestamp");
                localStorage.removeItem("scs_banner_dismissed_fingerprint");
                this.newItemsSinceDismissal = [];
                this.updateFloatingTriggerNewBadge();
            } catch (e) {}
        }

        /**
         * Add/remove a "NEW" tag on the floating trigger button
         * to visually tell visitors there are new announcements even while dismissed.
         */
        updateFloatingTriggerNewBadge() {
            if (!this.floatingTrigger) return;
            const hasNew = this.newItemsSinceDismissal && this.newItemsSinceDismissal.length > 0;

            // Remove existing new-tag if any
            const existing = this.floatingTrigger.querySelector(".scs-floating-new-tag");
            if (existing) existing.remove();

            if (hasNew) {
                this.floatingTrigger.classList.add("scs-has-new");
                const label = this.floatingTrigger.querySelector(".scs-floating-label");
                if (label) {
                    const tag = document.createElement("span");
                    tag.className = "scs-floating-new-tag";
                    tag.textContent = `${this.newItemsSinceDismissal.length} NEW`;
                    label.appendChild(tag);
                }
            } else {
                this.floatingTrigger.classList.remove("scs-has-new");
            }
        }

        getMediaType(url) {
            if (!url || typeof url !== "string") return "unknown";
            const cleanUrl = url.split("?")[0].split("#")[0].toLowerCase();
            const ext = cleanUrl.substring(cleanUrl.lastIndexOf(".") + 1);

            const imageExts = ["jpg", "jpeg", "png", "webp", "gif", "bmp", "svg"];
            const videoExts = ["mp4", "webm", "ogg", "mov"];
            const docExts = ["pdf"];

            if (imageExts.includes(ext)) return "image";
            if (videoExts.includes(ext)) return "video";
            if (docExts.includes(ext)) return "pdf";
            return "unknown";
        }

        formatTitle(url) {
            if (!url) return "";
            const filename = url.split("/").pop().split("?")[0].split("#")[0];
            const nameWithoutExt = filename.substring(0, filename.lastIndexOf(".")) || filename;
            return nameWithoutExt
                .replace(/[-_]+/g, " ")
                .replace(/\b\w/g, char => char.toUpperCase());
        }

        getTitle(url) {
            if (this.meta && this.meta[url] && this.meta[url].title) {
                return this.meta[url].title;
            }
            return this.formatTitle(url);
        }

        buildDOM() {
            // 1. Build floating trigger icon (Always visible at left corner)
            let trigger = document.getElementById("scsFloatingTrigger");
            if (!trigger) {
                trigger = document.createElement("div");
                trigger.id = "scsFloatingTrigger";
                trigger.className = "scs-floating-trigger";
                trigger.setAttribute("role", "button");
                trigger.setAttribute("aria-label", "View School Notices");
                trigger.setAttribute("title", "Click to view school notices");
                trigger.innerHTML = `
                    <div class="scs-floating-icon-wrap">
                        <i class="fas fa-bullhorn"></i>
                        <span class="scs-floating-count" id="scsFloatingCount">${this.mediaList.length}</span>
                    </div>
                    <span class="scs-floating-label">Recent Events/Notices</span>
                `;
                document.body.appendChild(trigger);
            }
            this.floatingTrigger = trigger;
            this.floatingCountEl = document.getElementById("scsFloatingCount");

            // 2. Build modal overlay if not already present
            let overlay = document.getElementById("scsBannerOverlay");
            if (!overlay) {
                overlay = document.createElement("div");
                overlay.id = "scsBannerOverlay";
                overlay.className = "scs-banner-overlay";
                overlay.setAttribute("role", "dialog");
                overlay.setAttribute("aria-modal", "true");
                overlay.setAttribute("aria-label", "School Announcement Banner");

                overlay.innerHTML = `
                    <div class="scs-banner-modal" id="scsBannerModal">
                        <!-- Top Toolbar / Header -->
                        <div class="scs-banner-header">
                            <div class="scs-banner-header-left">
                                <span class="scs-banner-badge"><i class="fas fa-bullhorn"></i>Events/Notices</span>
                                <span class="scs-banner-counter" id="scsBannerCounter">1 / 1</span>
                                <span class="scs-banner-title" id="scsBannerTitle">Announcement</span>
                            </div>

                            <div class="scs-banner-header-actions">
                                <!-- Image Zoom & Rotate Controls -->
                                <div class="scs-banner-zoom-toolbar" id="scsBannerZoomToolbar">
                                    <button type="button" class="scs-banner-zoom-btn" id="scsZoomOut" title="Zoom Out (-)"><i class="fas fa-search-minus"></i></button>
                                    <span class="scs-banner-zoom-level" id="scsZoomLevel">100%</span>
                                    <button type="button" class="scs-banner-zoom-btn" id="scsZoomIn" title="Zoom In (+)"><i class="fas fa-search-plus"></i></button>
                                    <button type="button" class="scs-banner-zoom-btn zoom-reset" id="scsZoomReset" title="Reset Zoom & Rotation (0)"><i class="fas fa-undo"></i></button>
                                    <button type="button" class="scs-banner-zoom-btn zoom-fit" id="scsZoomFit" title="Fit to Screen"><i class="fas fa-expand-arrows-alt"></i></button>
                                    <button type="button" class="scs-banner-zoom-btn zoom-rotate" id="scsRotate" title="Rotate 90° Clockwise (R)"><i class="fas fa-redo"></i></button>
                                </div>

                                <!-- Open in Another Tab Button (Images, PDFs, Videos) -->
                                <a href="#" target="_blank" rel="noopener noreferrer" class="scs-banner-btn" id="scsOpenNewTabBtn" title="Open media in another tab">
                                    <i class="fas fa-external-link-alt"></i> <span class="d-none d-md-inline">Open in Tab</span>
                                </a>

                                <!-- Close Button -->
                                <button type="button" class="scs-banner-btn scs-banner-btn-close" id="scsBannerClose" aria-label="Close popup" title="Close (Esc)">
                                    &times;
                                </button>
                            </div>
                        </div>

                        <!-- Media Viewport -->
                        <div class="scs-banner-body" id="scsBannerBody">
                            <div class="scs-banner-loader" id="scsBannerLoader"></div>
                            
                            <!-- Previous Button -->
                            <button type="button" class="scs-banner-nav prev" id="scsBannerPrev" aria-label="Previous banner" title="Previous (←)">
                                <i class="fas fa-chevron-left"></i>
                            </button>

                            <!-- Media Container -->
                            <div class="scs-banner-media-container" id="scsBannerMediaContainer"></div>

                            <!-- Next Button -->
                            <button type="button" class="scs-banner-nav next" id="scsBannerNext" aria-label="Next banner" title="Next (→)">
                                <i class="fas fa-chevron-right"></i>
                            </button>
                        </div>

                        <!-- Bottom Bar / Footer -->
                        <div class="scs-banner-footer">
                            <!-- Prominent Media Title / Caption Strip -->
                            <div class="scs-banner-footer-caption" id="scsBannerFooterCaption"></div>

                            <!-- Footer Navigation & Controls Row -->
                            <div class="scs-banner-footer-controls">
                                <div class="scs-banner-footer-left">
                                    <label class="scs-banner-checkbox-label">
                                        <input type="checkbox" id="scsDontShowAgain">
                                        <span>Don't show again today</span>
                                    </label>
                                </div>

                                <!-- Indicator Dots -->
                                <div class="scs-banner-dots" id="scsBannerDots"></div>

                                <div class="scs-banner-footer-hint">
                                    <span id="scsFooterHint"><i class="fas fa-mouse"></i> Scroll or drag to zoom & pan</span>
                                </div>
                            </div>
                        </div>
                    </div>
                `;

                document.body.appendChild(overlay);
            }

            this.overlay = overlay;
            this.modal = document.getElementById("scsBannerModal");
            this.bodyArea = document.getElementById("scsBannerBody");
            this.mediaContainer = document.getElementById("scsBannerMediaContainer");
            this.titleEl = document.getElementById("scsBannerTitle");
            this.counterEl = document.getElementById("scsBannerCounter");
            this.dotsContainer = document.getElementById("scsBannerDots");
            this.zoomToolbar = document.getElementById("scsBannerZoomToolbar");
            this.zoomLevelEl = document.getElementById("scsZoomLevel");
            this.rotateBtn = document.getElementById("scsRotate");
            this.openNewTabBtn = document.getElementById("scsOpenNewTabBtn");
            this.prevBtn = document.getElementById("scsBannerPrev");
            this.nextBtn = document.getElementById("scsBannerNext");
            this.closeBtn = document.getElementById("scsBannerClose");
            this.dontShowCheckbox = document.getElementById("scsDontShowAgain");
            this.loaderEl = document.getElementById("scsBannerLoader");
            this.footerHintEl = document.getElementById("scsFooterHint");
            this.footerCaptionEl = document.getElementById("scsBannerFooterCaption");

            this.buildDots();
        }

        buildDots() {
            if (!this.dotsContainer) return;
            this.dotsContainer.innerHTML = "";
            if (this.mediaList.length <= 1) {
                this.dotsContainer.style.display = "none";
                return;
            }
            this.dotsContainer.style.display = "flex";

            // Build a set of new-item indices for fast lookup
            const newIndices = new Set(
                (this.newItemsSinceDismissal || []).map(item => item.idx)
            );

            this.mediaList.forEach((_, idx) => {
                const dot = document.createElement("button");
                dot.type = "button";
                let cls = `scs-banner-dot ${idx === this.currentIndex ? "scs-active" : ""}`;
                if (newIndices.has(idx)) cls += " scs-dot-new";
                dot.className = cls;
                dot.setAttribute("aria-label", `Go to slide ${idx + 1}${newIndices.has(idx) ? " (New)" : ""}`);
                dot.addEventListener("click", (e) => {
                    e.stopPropagation();
                    this.goToIndex(idx);
                });
                this.dotsContainer.appendChild(dot);
            });
        }

        bindEvents() {
            // Close actions
            this.closeBtn.addEventListener("click", () => this.close());
            this.overlay.addEventListener("click", (e) => {
                // Close if backdrop clicked directly (not the modal or its children)
                if (e.target === this.overlay) {
                    this.close();
                }
            });

            // Navigation
            this.prevBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.prev();
            });

            this.nextBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.next();
            });

            // "Don't show again today" checkbox
            // Dismiss is stored when the viewer closes via close().
            // If the user un-checks, we clear the stored dismissal immediately.
            if (this.dontShowCheckbox) {
                this.dontShowCheckbox.addEventListener("change", (e) => {
                    if (!e.target.checked) {
                        this.clearDismiss();
                    }
                    // When checked, dismissal is saved by close() when the user closes the viewer,
                    // ensuring the media fingerprint is always up-to-date at dismiss time.
                });
            }

        // Floating trigger click – open banner viewer
        if (this.floatingTrigger) {
            this.floatingTrigger.addEventListener('click', (e) => {
                e.stopPropagation();
                this.open();
            });
        }

        // Rotate button – rotate image 90° clockwise per click
        if (this.rotateBtn) {
            this.rotateBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.rotation = (this.rotation + 90) % 360;
                this.applyTransform();
            });
        }



        // Keyboard navigation

            // Keyboard navigation
            document.addEventListener("keydown", (e) => {
                if (!this.isOpen) return;

                if (e.key === "Escape") {
                    this.close();
                } else if (e.key === "ArrowLeft") {
                    this.prev();
                } else if (e.key === "ArrowRight") {
                    this.next();
                } else if (e.key === "+" || e.key === "=") {
                    this.zoom(0.25);
                } else if (e.key === "-") {
                    this.zoom(-0.25);
                } else if (e.key === "0") {
                    this.resetZoom();
                }
            });

            // Zoom Toolbar Buttons
            document.getElementById("scsZoomIn").addEventListener("click", (e) => {
                e.stopPropagation();
                this.zoom(0.25);
            });
            document.getElementById("scsZoomOut").addEventListener("click", (e) => {
                e.stopPropagation();
                this.zoom(-0.25);
            });
            document.getElementById("scsZoomReset").addEventListener("click", (e) => {
                e.stopPropagation();
                this.resetZoom();
            });
            document.getElementById("scsZoomFit").addEventListener("click", (e) => {
                e.stopPropagation();
                this.resetZoom();
            });

            // Mouse wheel zoom inside body
            this.bodyArea.addEventListener("wheel", (e) => {
                const currentMedia = this.mediaList[this.currentIndex];
                if (this.getMediaType(currentMedia) !== "image") return;
                e.preventDefault();

                const delta = e.deltaY < 0 ? 0.2 : -0.2;
                this.zoom(delta);
            }, { passive: false });

            // Slideshow hover pause
            this.modal.addEventListener("mouseenter", () => {
                if (this.slideshowTimer) this.stopSlideshow();
            });
            this.modal.addEventListener("mouseleave", () => {
                if (this.isOpen && this.settings.slideshow) this.startSlideshow();
            });

            // Touch swipe on mobile for slides (when not zoomed)
            let touchStartX = 0;
            let touchStartY = 0;
            this.bodyArea.addEventListener("touchstart", (e) => {
                if (e.touches.length === 1) {
                    touchStartX = e.touches[0].clientX;
                    touchStartY = e.touches[0].clientY;
                }
            }, { passive: true });

            this.bodyArea.addEventListener("touchend", (e) => {
                if (this.zoomScale > 1.1) return; // Do not swipe if zoomed in
                if (e.changedTouches.length === 1) {
                    const diffX = e.changedTouches[0].clientX - touchStartX;
                    const diffY = e.changedTouches[0].clientY - touchStartY;
                    if (Math.abs(diffX) > 60 && Math.abs(diffY) < 50) {
                        if (diffX > 0) {
                            this.prev();
                        } else {
                            this.next();
                        }
                    }
                }
            }, { passive: true });
        }

        open(index = 0) {
            this.isOpen = true;
            document.body.classList.add("scs-banner-active");
            this.overlay.classList.add("scs-show");

            this.goToIndex(index);

            if (this.settings.slideshow) {
                this.startSlideshow();
            }

            // Ensure Tawk.to chat widget stays visible
            if (typeof Tawk_API !== "undefined" && typeof Tawk_API.showWidget === "function") {
                try { Tawk_API.showWidget(); } catch (e) {}
            }
        }

        close() {
            this.isOpen = false;
            this.stopSlideshow();
            this.stopActiveVideo();

            // Check if user selected "Don't show again" OR rememberClosed setting is on
            // Note: dismiss() now also stores a media fingerprint so new items can still
            // break through the suppression on the next visit.
            if ((this.dontShowCheckbox && this.dontShowCheckbox.checked) || this.settings.rememberClosed) {
                this.dismiss();
            }

            this.overlay.classList.remove("scs-show");
            document.body.classList.remove("scs-banner-active");

            // Ensure Tawk.to chat widget stays visible
            if (typeof Tawk_API !== "undefined" && typeof Tawk_API.showWidget === "function") {
                try { Tawk_API.showWidget(); } catch (e) {}
            }
        }

        prev() {
            let nextIdx = this.currentIndex - 1;
            if (nextIdx < 0) nextIdx = this.mediaList.length - 1;
            this.goToIndex(nextIdx);
        }

        next() {
            let nextIdx = this.currentIndex + 1;
            if (nextIdx >= this.mediaList.length) nextIdx = 0;
            this.goToIndex(nextIdx);
        }

        goToIndex(index) {
            if (index < 0 || index >= this.mediaList.length) return;
            this.stopActiveVideo();
            this.resetZoom();

            this.currentIndex = index;
            this.renderMedia(this.mediaList[index]);
            this.updateHeaderAndNav();
        }

        stopActiveVideo() {
            if (this.activeVideo) {
                try {
                    this.activeVideo.pause();
                    this.activeVideo.currentTime = 0;
                } catch (e) {}
                this.activeVideo = null;
            }
        }

        updateHeaderAndNav() {
            const currentMedia = this.mediaList[this.currentIndex];
            const type = this.getMediaType(currentMedia);

            // Determine if this slide is a newly added item
            const newIndices = new Set(
                (this.newItemsSinceDismissal || []).map(item => item.idx)
            );
            const isNewItem = newIndices.has(this.currentIndex);

            // Counter
            this.counterEl.textContent = `${this.currentIndex + 1} / ${this.mediaList.length}`;

            // Header badge: switch to glowing red "NEW" style when viewing a new slide
            const badgeEl = this.overlay ? this.overlay.querySelector(".scs-banner-badge") : null;
            if (badgeEl) {
                if (isNewItem) {
                    badgeEl.innerHTML = `<i class="fas fa-star-of-life"></i> NEW`;
                    badgeEl.classList.add("scs-badge-new");
                } else {
                    badgeEl.innerHTML = `<i class="fas fa-bullhorn"></i>Events/Notices`;
                    badgeEl.classList.remove("scs-badge-new", "scs-badge-updated");
                }
            }

            // Title (header) + footer caption with optional "NEW" pill
            const resolvedTitle = this.getTitle(currentMedia);
            this.titleEl.textContent = resolvedTitle;
            this.titleEl.title = resolvedTitle;
            if (this.footerCaptionEl) {
                if (isNewItem) {
                    this.footerCaptionEl.innerHTML =
                        `<span class="scs-caption-pill scs-pill-new">&#x2605; New</span>${resolvedTitle || ""}`;
                    this.footerCaptionEl.style.display = "block";
                } else if (resolvedTitle) {
                    this.footerCaptionEl.textContent = resolvedTitle;
                    this.footerCaptionEl.style.display = "block";
                } else {
                    this.footerCaptionEl.textContent = "";
                    this.footerCaptionEl.style.display = "none";
                }
            }

            // Nav buttons state (if only 1 item, disable both)
            if (this.mediaList.length <= 1) {
                this.prevBtn.classList.add("scs-disabled");
                this.nextBtn.classList.add("scs-disabled");
            } else {
                this.prevBtn.classList.remove("scs-disabled");
                this.nextBtn.classList.remove("scs-disabled");
            }

            // Dots — keep scs-dot-new class on new-item dots; only toggle active state
            const dots = this.dotsContainer.querySelectorAll(".scs-banner-dot");
            dots.forEach((dot, idx) => {
                dot.classList.toggle("scs-active", idx === this.currentIndex);
            });

            // Toolbars & Hints
            if (type === "image") {
                this.zoomToolbar.classList.add("scs-active");
                if (this.rotateBtn) this.rotateBtn.style.display = "inline-flex";
                if (this.openNewTabBtn) this.openNewTabBtn.style.display = "none";
                this.footerHintEl.innerHTML = `<i class="fas fa-mouse"></i> Scroll or drag to zoom & pan`;
            } else if (type === "pdf") {
                this.zoomToolbar.classList.remove("scs-active");
                if (this.rotateBtn) this.rotateBtn.style.display = "none";
                if (this.openNewTabBtn) {
                    this.openNewTabBtn.style.display = "inline-flex";
                    this.openNewTabBtn.href = currentMedia;
                }
                this.footerHintEl.innerHTML = `<i class="fas fa-file-pdf"></i> Scroll inside document to read`;
            } else if (type === "video") {
                this.zoomToolbar.classList.remove("scs-active");
                if (this.rotateBtn) this.rotateBtn.style.display = "none";
                if (this.openNewTabBtn) this.openNewTabBtn.style.display = "none";
                this.footerHintEl.innerHTML = `<i class="fas fa-play-circle"></i> HTML5 Video Player`;
            } else {
                this.zoomToolbar.classList.remove("scs-active");
                if (this.rotateBtn) this.rotateBtn.style.display = "none";
                if (this.openNewTabBtn) this.openNewTabBtn.style.display = "none";
                this.footerHintEl.innerHTML = "";
            }
        }


        setModalMode(modeClass) {
            this.modal.classList.remove(
                "scs-mode-image-portrait",
                "scs-mode-image-landscape",
                "scs-mode-image-square",
                "scs-mode-video",
                "scs-mode-video-portrait",
                "scs-mode-pdf"
            );
            if (modeClass) {
                this.modal.classList.add(modeClass);
            }
        }

        renderMedia(url) {
            const type = this.getMediaType(url);
            this.mediaContainer.innerHTML = "";
            this.loaderEl.classList.add("scs-active");

            if (type === "image") {
                this.renderImage(url);
            } else if (type === "video") {
                this.renderVideo(url);
            } else if (type === "pdf") {
                this.renderPdf(url);
            } else {
                this.renderUnknown(url);
            }
        }

        renderImage(url) {
            const wrapper = document.createElement("div");
            wrapper.className = "scs-banner-image-wrapper";

            const img = document.createElement("img");
            img.className = "scs-banner-img";
            img.alt = this.formatTitle(url);

            img.onload = () => {
                this.loaderEl.classList.remove("scs-active");

                // Determine aspect ratio to adapt modal size
                const width = img.naturalWidth || 800;
                const height = img.naturalHeight || 600;
                const ratio = width / height;

                if (ratio < 0.85) {
                    this.setModalMode("scs-mode-image-portrait");
                } else if (ratio > 1.2) {
                    this.setModalMode("scs-mode-image-landscape");
                } else {
                    this.setModalMode("scs-mode-image-square");
                }
            };

            img.onerror = () => {
                this.loaderEl.classList.remove("scs-active");
                this.renderError("Unable to load image: " + url);
            };

            img.src = url;
            wrapper.appendChild(img);
            this.mediaContainer.appendChild(wrapper);

            // Bind Pan & Zoom listeners on image
            this.setupImagePanZoom(img, wrapper);
        }

        renderVideo(url) {
            this.setModalMode("scs-mode-video");

            const wrapper = document.createElement("div");
            wrapper.className = "scs-banner-video-wrapper";

            // ── Video Element ─────────────────────────────────────────────
            const video = document.createElement("video");
            video.className = "scs-banner-video";
            video.playsInline = true;
            video.preload = "metadata";
            // Use custom controls – native controls hidden
            video.controls = false;

            const source = document.createElement("source");
            source.src = url;
            const ext = url.split(".").pop().toLowerCase();
            source.type = ext === "mp4" ? "video/mp4" : ext === "webm" ? "video/webm" : "video/ogg";
            video.appendChild(source);

            // ── Custom Controls Bar ───────────────────────────────────────
            const controls = document.createElement("div");
            controls.className = "scs-video-controls";

            // Play / Pause
            const playBtn = document.createElement("button");
            playBtn.className = "scs-video-btn scs-video-play";
            playBtn.setAttribute("aria-label", "Play/Pause");
            playBtn.innerHTML = `<i class="fas fa-play"></i>`;

            // Current time
            const timeEl = document.createElement("span");
            timeEl.className = "scs-video-time";
            timeEl.textContent = "0:00 / 0:00";

            // Progress bar track
            const progressTrack = document.createElement("div");
            progressTrack.className = "scs-video-progress-track";
            const progressFill = document.createElement("div");
            progressFill.className = "scs-video-progress-fill";
            const progressThumb = document.createElement("div");
            progressThumb.className = "scs-video-progress-thumb";
            progressTrack.appendChild(progressFill);
            progressTrack.appendChild(progressThumb);

            // Mute button
            const muteBtn = document.createElement("button");
            muteBtn.className = "scs-video-btn scs-video-mute";
            muteBtn.setAttribute("aria-label", "Mute/Unmute");
            muteBtn.innerHTML = `<i class="fas fa-volume-up"></i>`;

            // Volume slider
            const volumeSlider = document.createElement("input");
            volumeSlider.type = "range";
            volumeSlider.className = "scs-video-volume";
            volumeSlider.min = "0";
            volumeSlider.max = "1";
            volumeSlider.step = "0.05";
            volumeSlider.value = "1";
            volumeSlider.setAttribute("aria-label", "Volume");

            controls.appendChild(playBtn);
            controls.appendChild(timeEl);
            controls.appendChild(progressTrack);
            controls.appendChild(muteBtn);
            controls.appendChild(volumeSlider);

            wrapper.appendChild(video);
            wrapper.appendChild(controls);
            this.mediaContainer.appendChild(wrapper);

            this.activeVideo = video;

            // ── Helpers ───────────────────────────────────────────────────
            const fmt = (s) => {
                const m = Math.floor(s / 60);
                const sec = Math.floor(s % 60);
                return `${m}:${sec.toString().padStart(2, "0")}`;
            };

            const updatePlay = () => {
                playBtn.innerHTML = video.paused
                    ? `<i class="fas fa-play"></i>`
                    : `<i class="fas fa-pause"></i>`;
            };

            const updateVolume = () => {
                muteBtn.innerHTML = (video.muted || video.volume === 0)
                    ? `<i class="fas fa-volume-mute"></i>`
                    : video.volume < 0.5
                        ? `<i class="fas fa-volume-down"></i>`
                        : `<i class="fas fa-volume-up"></i>`;
                volumeSlider.value = video.muted ? 0 : video.volume;
            };

            const updateProgress = () => {
                if (!video.duration) return;
                const pct = (video.currentTime / video.duration) * 100;
                progressFill.style.width = pct + "%";
                progressThumb.style.left = pct + "%";
                timeEl.textContent = `${fmt(video.currentTime)} / ${fmt(video.duration)}`;
            };

            // ── Events ────────────────────────────────────────────────────
            video.addEventListener("loadedmetadata", () => {
                this.loaderEl.classList.remove("scs-active");
                timeEl.textContent = `0:00 / ${fmt(video.duration)}`;

                // Dynamically adapt modal size to video aspect ratio
                if (video.videoWidth && video.videoHeight) {
                    const vRatio = video.videoWidth / video.videoHeight;
                    if (vRatio < 0.85) {
                        this.setModalMode("scs-mode-video-portrait");
                    } else {
                        this.setModalMode("scs-mode-video");
                    }
                }
            });

            video.onloadeddata = () => { this.loaderEl.classList.remove("scs-active"); };

            video.onerror = () => {
                this.loaderEl.classList.remove("scs-active");
                this.renderError("Unable to play video: " + url);
            };

            video.addEventListener("play", () => {
                updatePlay();
                this.stopSlideshow();
            });
            video.addEventListener("pause", updatePlay);
            video.addEventListener("ended", () => {
                updatePlay();
                if (this.settings.slideshow) this.startSlideshow();
            });
            video.addEventListener("timeupdate", updateProgress);
            video.addEventListener("volumechange", updateVolume);

            // Play / Pause button click
            playBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                video.paused ? video.play() : video.pause();
            });

            // Mute toggle
            muteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                video.muted = !video.muted;
                updateVolume();
            });

            // Volume change
            volumeSlider.addEventListener("input", (e) => {
                e.stopPropagation();
                video.volume = parseFloat(volumeSlider.value);
                video.muted = video.volume === 0;
                updateVolume();
            });

            // Seek on progress bar click/drag
            const seek = (e) => {
                e.stopPropagation();
                const rect = progressTrack.getBoundingClientRect();
                const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
                const pct = Math.min(Math.max(x / rect.width, 0), 1);
                video.currentTime = pct * video.duration;
            };

            progressTrack.addEventListener("click", seek);
            progressTrack.addEventListener("touchstart", seek, { passive: true });

            let seekDragging = false;
            progressThumb.addEventListener("mousedown", (e) => { seekDragging = true; e.preventDefault(); });
            window.addEventListener("mousemove", (e) => {
                if (!seekDragging) return;
                seek(e);
            });
            window.addEventListener("mouseup", () => { seekDragging = false; });

            // Click on video to play/pause
            video.addEventListener("click", (e) => {
                e.stopPropagation();
                video.paused ? video.play() : video.pause();
            });
        }


        renderPdf(url) {
            this.setModalMode("scs-mode-pdf");

            const wrapper = document.createElement("div");
            wrapper.className = "scs-banner-pdf-wrapper";

            // Fallback for mobile devices that restrict inline PDFs
            const fallback = document.createElement("div");
            fallback.className = "scs-banner-pdf-fallback";
            fallback.innerHTML = `
                <i class="fas fa-file-pdf fa-3x" style="color: #ff5252;"></i>
                <h4>${this.formatTitle(url)}</h4>
                <p>If the PDF does not display directly in your browser, tap below to view or download it:</p>
                <a href="${url}" target="_blank" class="scs-banner-btn scs-banner-btn-primary">
                    <i class="fas fa-file-download"></i> View PDF Document
                </a>
            `;

            const iframe = document.createElement("iframe");
            iframe.className = "scs-banner-pdf-frame";
            iframe.src = `${url}#toolbar=1&navpanes=0&scrollbar=1`;
            iframe.title = this.formatTitle(url);

            iframe.onload = () => {
                this.loaderEl.classList.remove("scs-active");
            };

            iframe.onerror = () => {
                this.loaderEl.classList.remove("scs-active");
                fallback.style.display = "flex";
            };

            wrapper.appendChild(iframe);
            wrapper.appendChild(fallback);
            this.mediaContainer.appendChild(wrapper);

            // Timeout loader in case iframe onload event is suppressed by browser PDF viewer
            setTimeout(() => {
                this.loaderEl.classList.remove("scs-active");
            }, 1200);
        }

        renderUnknown(url) {
            this.loaderEl.classList.remove("scs-active");
            this.setModalMode("scs-mode-image-square");
            this.mediaContainer.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: #fff;">
                    <i class="fas fa-paperclip fa-3x mb-3" style="color: var(--scs-primary);"></i>
                    <h4>${this.formatTitle(url)}</h4>
                    <p>Preview is not available for this file type.</p>
                    <a href="${url}" target="_blank" class="scs-banner-btn scs-banner-btn-primary">Download File</a>
                </div>
            `;
        }

        renderError(message) {
            this.loaderEl.classList.remove("scs-active");
            this.setModalMode("scs-mode-image-square");
            this.mediaContainer.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: #ff6b7a;">
                    <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                    <h4>Content Unavailable</h4>
                    <p>${message}</p>
                </div>
            `;
        }

        // ==========================================
        // Image Zoom & Pan Engine
        // ==========================================
        setupImagePanZoom(img, wrapper) {
            this.currentImg = img;
            this.resetZoom();

            // Mouse Drag to Pan
            const startDrag = (e) => {
                if (this.zoomScale <= 1) return;
                this.isDragging = true;
                this.hasMovedDrag = false;
                this.dragStartX = e.clientX - this.panX;
                this.dragStartY = e.clientY - this.panY;
                img.classList.add("scs-dragging");
                e.preventDefault();
            };

            const doDrag = (e) => {
                if (!this.isDragging) return;
                this.hasMovedDrag = true;
                this.panX = e.clientX - this.dragStartX;
                this.panY = e.clientY - this.dragStartY;
                this.applyTransform();
            };

            const stopDrag = () => {
                if (this.isDragging) {
                    this.isDragging = false;
                    img.classList.remove("scs-dragging");
                }
            };

            wrapper.addEventListener("mousedown", startDrag);
            window.addEventListener("mousemove", doDrag);
            window.addEventListener("mouseup", stopDrag);

            // Double Click to Toggle Zoom
            wrapper.addEventListener("dblclick", (e) => {
                e.preventDefault();
                if (this.zoomScale > 1.2) {
                    this.resetZoom();
                } else {
                    this.zoomScale = 2.0;
                    this.panX = 0;
                    this.panY = 0;
                    this.applyTransform();
                }
            });

            // Touch Drag & Pinch Zoom for Mobile
            let touchInitialX = 0;
            let touchInitialY = 0;

            const getTouchDistance = (touches) => {
                const dx = touches[0].clientX - touches[1].clientX;
                const dy = touches[0].clientY - touches[1].clientY;
                return Math.sqrt(dx * dx + dy * dy);
            };

            wrapper.addEventListener("touchstart", (e) => {
                if (e.touches.length === 1 && this.zoomScale > 1) {
                    this.isDragging = true;
                    touchInitialX = e.touches[0].clientX - this.panX;
                    touchInitialY = e.touches[0].clientY - this.panY;
                    img.classList.add("scs-dragging");
                } else if (e.touches.length === 2) {
                    this.initialPinchDistance = getTouchDistance(e.touches);
                    this.initialPinchScale = this.zoomScale;
                }
            }, { passive: true });

            wrapper.addEventListener("touchmove", (e) => {
                if (e.touches.length === 1 && this.isDragging && this.zoomScale > 1) {
                    this.panX = e.touches[0].clientX - touchInitialX;
                    this.panY = e.touches[0].clientY - touchInitialY;
                    this.applyTransform();
                } else if (e.touches.length === 2 && this.initialPinchDistance) {
                    const currentDist = getTouchDistance(e.touches);
                    const factor = currentDist / this.initialPinchDistance;
                    this.zoomScale = Math.min(this.maxScale, Math.max(this.minScale, this.initialPinchScale * factor));
                    this.applyTransform();
                }
            }, { passive: true });

            wrapper.addEventListener("touchend", () => {
                this.isDragging = false;
                this.initialPinchDistance = null;
                img.classList.remove("scs-dragging");
            }, { passive: true });
        }

        zoom(step) {
            const prevScale = this.zoomScale;
            this.zoomScale = Math.min(this.maxScale, Math.max(this.minScale, +(this.zoomScale + step).toFixed(2)));

            // If zoomed back to 1.0 or below, center image
            if (this.zoomScale <= 1.0) {
                this.panX = 0;
                this.panY = 0;
            } else {
                // Adjust pan proportionally
                const ratio = this.zoomScale / prevScale;
                this.panX = this.panX * ratio;
                this.panY = this.panY * ratio;
            }

            this.applyTransform();
        }

        resetZoom() {
            this.zoomScale = 1;
            this.panX = 0;
            this.panY = 0;
            this.rotation = 0;
            this.applyTransform();
        }

        applyTransform() {
            if (!this.currentImg) return;
            this.currentImg.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.zoomScale}) rotate(${this.rotation}deg)`;
            if (this.zoomLevelEl) {
                this.zoomLevelEl.textContent = `${Math.round(this.zoomScale * 100)}%`;
            }
        }

        // ==========================================
        // Slideshow Engine
        // ==========================================
        startSlideshow() {
            this.stopSlideshow();
            this.slideshowTimer = setInterval(() => {
                if (this.isOpen && !this.activeVideo) {
                    this.next();
                }
            }, this.settings.slideshowInterval || 5000);
        }

        stopSlideshow() {
            if (this.slideshowTimer) {
                clearInterval(this.slideshowTimer);
                this.slideshowTimer = null;
            }
        }
    }

    // Auto-initialize when document is ready
    let instance = null;
    function initBanner() {
        if (!instance) {
            instance = new ScsBannerViewer();
            window.ScsBanner = instance;
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initBanner);
    } else {
        initBanner();
    }
})();
