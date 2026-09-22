/* ============================================================
 * Latest News Ticker - Shree Chautara Mavi
 * Horizontal headline rotator with next / prev / play / pause.
 * Pulls the 3 most recent notice titles from notice.html
 * (same origin, no backend required).
 * ============================================================ */
(function () {
    "use strict";

    var bar = document.getElementById("newsTicker");
    if (!bar) return;

    var track = document.getElementById("tickerTrack");
    var viewport = document.getElementById("tickerViewport");
    var prevBtn = document.getElementById("tickerPrev");
    var nextBtn = document.getElementById("tickerNext");
    var playBtn = document.getElementById("tickerPlayPause");

    var titles = [];
    var pos = 0;
    var n = 0;
    var timer = null;
    var playing = true;
    var INTERVAL = 4000;

    // Embedded snapshot of the latest notices. Used immediately so the ticker
    // always shows titles (even when opened as a local file:// where fetch()
    // is blocked). Replaced automatically with live data from notice.html
    // whenever the page is served over HTTP. Each item carries the full notice
    // data so the detail page can open the notice without fetching anything.
    var FALLBACK_NOTICES = [
        {
            "id": "notice-8e08c22339",
            "title": "CTEVT 2nd and 4th Sem (R & B) Routine - 2083",
            "content": "डिप्लोमा/प्रमाणपत्र तहको नियमित तथा आंशिक परीक्षा २०८३ को संशोधित परीक्षा तालिका सम्बन्धी अत्यन्त जरुरी सूचना",
            "date": "2083/06/06",
            "badge": "⭐ Important",
            "file": "notices/CTEVT 2nd and 4th Sem R  B Routine - 2083_b70f239e.jpg"
        },
        {
            "id": "notice-e864fb8731",
            "title": "कक्षा ११ को विषय",
            "content": "कक्षा ११ को विषय दर्ता फाराम भर्ने भराउने सम्बन्धमा ।",
            "date": "2083/06/06",
            "badge": "⭐ Important",
            "file": "notices/jpg_63aa50c6.jpg"
        },
        {
            "id": "notice-230ea25894",
            "title": "CTEVT External Practical Examination",
            "content": "CTEVT External Practical Examination for 4th sem - 2083",
            "date": "2083/06/06",
            "badge": "⭐ Important",
            "file": "notices/New_Doc_09-21-2026_1131_302157b7.jpg"
        }
    ];

    function goTo(index, smooth) {
        pos = index;
        if (smooth === false) track.style.transition = "none";
        track.style.transform = "translateX(" + (-pos * 100) + "%)";
        if (smooth === false) {
            void track.offsetWidth;
            track.style.transition = "";
        }
    }

    function step() {
        if (!n) return;
        if (pos === n) {
            goTo(0, false);
            goTo(1);
        } else if (pos === n - 1) {
            goTo(n);
        } else {
            goTo(pos + 1);
        }
    }

    function restart() {
        stopTimer();
        if (playing) startTimer();
    }

    function startTimer() {
        stopTimer();
        timer = setInterval(step, INTERVAL);
    }

    function stopTimer() {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
    }

    // Every headline links to the dedicated detail page for that single notice.
    // The id is the primary key; title/date are passed along so the detail page
    // can still render a usable result when it cannot fetch notice.html.
    function noticeHref(t) {
        if (!t.id) return "notice.html";
        var url = "notice_detail.html?id=" + encodeURIComponent(t.id);
        if (t.title) url += "&title=" + encodeURIComponent(t.title);
        if (t.date) url += "&date=" + encodeURIComponent(t.date);
        if (t.badge) url += "&badge=" + encodeURIComponent(t.badge);
        // Always send content (even empty) so the detail page never needs to fetch.
        url += "&content=" + encodeURIComponent(t.content || "");
        if (t.file) url += "&file=" + encodeURIComponent(t.file);
        return url;
    }

    function buildTrack() {
        track.innerHTML = "";
        if (!titles.length) {
            var empty = document.createElement("div");
            empty.className = "ticker-item";
            var emptyA = document.createElement("a");
            emptyA.href = "notice.html";
            emptyA.target = "_blank";
            emptyA.textContent = "No new notices at the moment. Click here to view all notices.";
            empty.appendChild(emptyA);
            track.appendChild(empty);
            return;
        }
        for (var c = 0; c < 2; c++) {
            titles.forEach(function (t) {
                var item = document.createElement("div");
                item.className = "ticker-item";
                var a = document.createElement("a");
                a.href = noticeHref(t);
                a.target = "_blank";
                a.textContent = t.title;
                if (t.date) a.setAttribute("title", "Published on " + t.date);
                item.appendChild(a);
                track.appendChild(item);
            });
        }
        pos = 0;
        goTo(0, false);
    }

    // Reflect the current playing state on the toggle button. Font Awesome
    // (5+) auto-replaces <i class="fa fa-pause"> with inline <svg> elements,
    // so the icons are looked up here every time instead of being cached.
    // Both the <i> and the generated <svg> keep the "fa-pause"/"fa-play" class.
    function setPlayState() {
        if (!playBtn) return;
        var pauseIcon = playBtn.querySelector(".fa-pause");
        var playIco = playBtn.querySelector(".fa-play");
        if (pauseIcon) pauseIcon.style.display = playing ? "" : "none";
        if (playIco) playIco.style.display = playing ? "none" : "";
        playBtn.title = playing ? "Pause" : "Play";
        playBtn.setAttribute("aria-label", playing ? "Pause ticker" : "Play ticker");
        playBtn.classList.toggle("is-paused", !playing);
    }

    function bindControls() {
        if (prevBtn) {
            prevBtn.addEventListener("click", function () {
                if (!n) return;
                if (pos === 0) {
                    goTo(n, false);
                    goTo(n - 1);
                } else {
                    goTo(pos - 1);
                }
                restart();
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener("click", function () {
                if (!n) return;
                step();
                restart();
            });
        }

        if (playBtn) {
            playBtn.addEventListener("click", function () {
                playing = !playing;
                setPlayState();
                if (playing) {
                    startTimer();
                } else {
                    stopTimer();
                }
            });
        }

        if (viewport) {
            viewport.addEventListener("mouseenter", stopTimer);
            viewport.addEventListener("mouseleave", function () {
                if (playing) startTimer();
            });
        }
    }

    function applyTitles(list) {
        titles = list;
        n = titles.length;
        buildTrack();
        stopTimer();
        if (n > 1 && playing) {
            startTimer();
        }
        setPlayState();
    }

    function loadNotices() {
        fetch("notice.html?t=" + Date.now(), { cache: "no-store" })
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP " + res.status);
                return res.text();
            })
            .then(function (html) {
                var doc = new DOMParser().parseFromString(html, "text/html");
                var rows = doc.querySelectorAll("#noticeTable tbody tr");
                var list = [];
                rows.forEach(function (row) {
                    var titleEl = row.querySelector('td[data-label="Title"]');
                    if (!titleEl) return;
                    var title = titleEl.textContent.replace(/\s+/g, " ").trim();
                    if (!title) return;
                    var dateEl = row.querySelector('td[data-label="Date"]');
                    var date = dateEl
                        ? (dateEl.getAttribute("data-date") || dateEl.textContent.replace(/\s+/g, " ").trim())
                        : "";
                    var sort = dateEl ? (dateEl.getAttribute("data-sort") || "") : "";
                    var rowId = row.getAttribute("id") || "";
                    var contentEl = row.querySelector("div.notice-content");
                    var badgeEl = row.querySelector("span.badge");
                    var fileEl = row.querySelector("a.download-link");
                    list.push({
                        title: title,
                        date: date,
                        sort: sort,
                        id: rowId,
                        content: contentEl ? contentEl.textContent.replace(/\s+/g, " ").trim() : "",
                        badge: badgeEl ? badgeEl.textContent.replace(/\s+/g, " ").trim() : "",
                        file: fileEl ? (fileEl.getAttribute("href") || "") : ""
                    });
                });
                list.sort(function (a, b) {
                    return (b.sort || "").localeCompare(a.sort || "");
                });
                if (!list.length) throw new Error("No notices found in notice.html");
                applyTitles(list.slice(0, 3));
            })
            .catch(function (err) {
                console.warn("[NewsTicker] Using embedded snapshot (fetch failed:", err.message, ")");
            });
    }

    bindControls();
    applyTitles(FALLBACK_NOTICES);
    loadNotices();
})();