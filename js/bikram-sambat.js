(function (global) {
    "use strict";

    var MS_PER_DAY = 86400000;
    var BS_EPOCH_TS = -1789990200000; // 1913-04-13 AD = 1970-01-01 BS (local time)
    var BS_YEAR_ZERO = 1970;
    var MONTH_NAMES = [
        "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
        "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"
    ];
    var ENCODED_MONTH_LENGTHS = [
        5315258,5314490,9459438,8673005,5315258,5315066,9459438,8673005,
        5315258,5314298,9459438,5327594,5315258,5314298,9459438,5327594,
        5315258,5314286,9459438,5315306,5315258,5314286,8673006,5315306,
        5315258,5265134,8673006,5315258,5315258,9459438,8673005,5315258,
        5314298,9459438,8673005,5315258,5314298,9459438,8473322,5315258,
        5314298,9459438,5327594,5315258,5314298,9459438,5327594,5315258,
        5314286,8673006,5315306,5315258,5265134,8673006,5315306,5315258,
        9459438,8673005,5315258,5314490,9459438,8673005,5315258,5314298,
        9459438,8473325,5315258,5314298,9459438,5327594,5315258,5314298,
        9459438,5327594,5315258,5314286,9459438,5315306,5315258,5265134,
        8673006,5315306,5315258,5265134,8673006,5315258,5314490,9459438,
        8673005,5315258,5314298,9459438,8669933,5315258,5314298,9459438,
        8473322,5315258,5314298,9459438,5327594,5315258,5314286,9459438,
        5315306,5315258,5265134,8673006,5315306,5315258,5265134,8673006,
        5315258,5315258,5527226,5528046,5527277,5528250,5528057,5527277,
        5527277
    ];

    function daysInMonth(year, month) {
        if (month < 1 || month > 12) {
            throw new Error("Invalid month value " + month);
        }
        var delta = ENCODED_MONTH_LENGTHS[year - BS_YEAR_ZERO];
        if (typeof delta === "undefined") {
            throw new Error("No data for year: " + year + " BS");
        }
        return 29 + ((delta >>> (((month - 1) << 1))) & 3);
    }

    function zPad(x) {
        return x > 9 ? x : "0" + x;
    }

    function toBik(dateOrString) {
        var date = typeof dateOrString === "string" ? new Date(dateOrString) : dateOrString;
        if (!(date instanceof Date) || isNaN(date.getTime())) {
            throw new Error("Invalid date: " + dateOrString);
        }
        var ts = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
        var days = Math.floor((ts - BS_EPOCH_TS) / MS_PER_DAY) + 1;
        var year = BS_YEAR_ZERO;
        while (days > 0) {
            for (var m = 1; m <= 12; m++) {
                var dMax = daysInMonth(year, m);
                if (days <= dMax) {
                    return { year: year, month: m, day: days };
                }
                days -= dMax;
            }
            year++;
        }
        throw new Error("Date outside supported range: " + dateOrString + " AD");
    }

    function toBikEuro(dateOrString) {
        var d = toBik(dateOrString);
        return d.year + "-" + zPad(d.month) + "-" + zPad(d.day);
    }

    function toBikText(dateOrString) {
        var d = toBik(dateOrString);
        return d.day + " " + MONTH_NAMES[d.month - 1] + ", " + d.year;
    }

    global.BikramSambat = {
        toBik: toBik,
        toBikEuro: toBikEuro,
        toBikText: toBikText,
        daysInMonth: daysInMonth
    };
    global.toBikEuro = toBikEuro;
})(window);