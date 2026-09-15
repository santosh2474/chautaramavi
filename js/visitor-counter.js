(function () {
    "use strict";

    var DISPLAY_ID = "totalVisitors";
    var CACHE_STORAGE_KEY = "cms_total_visitors";
    var COUNTED_STORAGE_KEY = "cms_visitor_counted_date";
    var COUNTER_KEY = "chautaramavi-school/visitors";
    var API_BASE = "https://countapi.mileshilliard.com/api/v1";

    function render(value) {
        var el = document.getElementById(DISPLAY_ID);
        if (!el) {
            return;
        }
        var n = parseInt(value, 10);
        if (isNaN(n)) {
            el.textContent = "\u2026";
        } else {
            el.textContent = n.toLocaleString();
        }
    }

    function readCached() {
        try {
            var value = parseInt(localStorage.getItem(CACHE_STORAGE_KEY), 10);
            return isNaN(value) ? null : value;
        } catch (e) {
            return null;
        }
    }

    function saveCached(value) {
        try {
            localStorage.setItem(CACHE_STORAGE_KEY, String(value));
        } catch (e) {}
    }

    function isCountedToday() {
        try {
            return localStorage.getItem(COUNTED_STORAGE_KEY) === new Date().toDateString();
        } catch (e) {
            return false;
        }
    }

    function markCountedToday() {
        try {
            localStorage.setItem(COUNTED_STORAGE_KEY, new Date().toDateString());
        } catch (e) {}
    }

    function fallbackToLocal() {
        var base = readCached() || 0;
        var value = base;
        if (!isCountedToday()) {
            value = base + 1;
            markCountedToday();
        }
        saveCached(value);
        render(value);
    }

    function fetchCount(path, onSuccess) {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", API_BASE + path, true);
        xhr.timeout = 8000;
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) {
                return;
            }
            if (xhr.status === 200) {
                try {
                    var data = JSON.parse(xhr.responseText);
                    if (data && data.value !== undefined) {
                        onSuccess(data.value);
                        return;
                    }
                } catch (e) {}
            }
            fallbackToLocal();
        };
        xhr.onerror = fallbackToLocal;
        xhr.ontimeout = fallbackToLocal;
        xhr.send();
    }

    function hitCount() {
        fetchCount("/hit/" + COUNTER_KEY, function (value) {
            markCountedToday();
            saveCached(value);
            render(value);
        });
    }

    function getCount() {
        fetchCount("/get/" + COUNTER_KEY, function (value) {
            saveCached(value);
            render(value);
        });
    }

    function start() {
        if (!document.getElementById(DISPLAY_ID)) {
            return;
        }
        render(readCached() || "\u2026");
        if (isCountedToday()) {
            getCount();
        } else {
            hitCount();
        }
    }

    window.TotalVisitors = {
        start: start,
        hit: hitCount,
        get: getCount
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();