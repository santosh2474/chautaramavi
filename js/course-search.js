(function () {
    "use strict";

    /*
     * Header course search.
     *
     * Any element marked with data-course-search is treated as a search widget.
     * Inside it, the keyword input and the search button are detected
     * automatically, so the same script works on every page.
     */

    var COURSES = [
        {
            title: "Diploma in Computer Engineering",
            url: "detail.html",
            keywords: [
                "diploma",
                "diploma in computer engineering",
                "computer",
                "computer engineering",
                "engineering",
                "ctevt",
                "it",
                "information technology",
                "software",
                "programming",
                "hardware"
            ]
        },
        {
            title: "+2 Science",
            url: "detail2.html",
            keywords: [
                "+2 science",
                "science",
                "plus two science",
                "2 science",
                "grade 11 science",
                "grade 12 science",
                "neb science",
                "physics",
                "chemistry",
                "biology",
                "mathematics",
                "maths"
            ]
        },
        {
            title: "+2 Education",
            url: "detail3.html",
            keywords: [
                "+2 education",
                "education",
                "plus two education",
                "2 education",
                "grade 11 education",
                "grade 12 education",
                "neb education",
                "teaching",
                "pedagogy"
            ]
        },
        {
            title: "School (Nursery to Grade 10)",
            url: "detail4.html",
            keywords: [
                "school",
                "school education",
                "nursery",
                "kindergarten",
                "montessori",
                "primary",
                "primary level",
                "secondary",
                "secondary level",
                "basic level",
                "english medium",
                "nursery to grade 10"
            ]
        }
    ];

    // "class 1" ... "class 10" and "grade 1" ... "grade 10"
    for (var i = 1; i <= 10; i++) {
        COURSES[3].keywords.push("class " + i);
        COURSES[3].keywords.push("grade " + i);
    }

    function normalize(text) {
        return String(text || "")
            .toLowerCase()
            .replace(/&/g, " and ")
            .replace(/plus\s+two/g, " +2 ")
            .replace(/\+2/g, " +2 ")
            .replace(/[^a-z0-9+\s]/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function hasPhrase(text, phrase) {
        if (!text || !phrase) {
            return false;
        }
        return (" " + text + " ").indexOf(" " + phrase + " ") !== -1;
    }

    COURSES.forEach(function (course) {
        course.normalizedKeywords = course.keywords
            .map(normalize)
            .filter(function (keyword, index, list) {
                return keyword && list.indexOf(keyword) === index;
            });
    });

    function scoreCourse(course, query) {
        var score = 0;
        var queryTokens = query.split(" ").filter(function (token) {
            return token.length > 1;
        });

        course.normalizedKeywords.forEach(function (keyword) {
            if (query === keyword) {
                score += 120;
                return;
            }

            if (hasPhrase(query, keyword)) {
                score += 25 + keyword.split(" ").length * 6;
            } else if (keyword.length >= 3 && hasPhrase(keyword, query)) {
                score += 12;
            }

            var keywordTokens = keyword.split(" ");
            queryTokens.forEach(function (token) {
                if (keywordTokens.indexOf(token) !== -1) {
                    score += 5;
                }
            });
        });

        return score;
    }

    function findMatches(query) {
        var normalizedQuery = normalize(query);

        if (!normalizedQuery) {
            return [];
        }

        var scored = COURSES.map(function (course) {
            return {
                course: course,
                score: scoreCourse(course, normalizedQuery)
            };
        }).filter(function (entry) {
            return entry.score > 0;
        });

        if (!scored.length) {
            return [];
        }

        scored.sort(function (a, b) {
            return b.score - a.score;
        });

        var bestScore = scored[0].score;

        // Treat near-equal results as a tie so the user can pick the course.
        return scored
            .filter(function (entry) {
                return entry.score >= bestScore - 2;
            })
            .map(function (entry) {
                return entry.course;
            });
    }

    function initSearchWidget(widget) {
        var input = widget.querySelector("[data-course-search-input]") ||
            widget.querySelector("input[type='text'], input[type='search']");
        var button = widget.querySelector("[data-course-search-button]") ||
            widget.querySelector(".input-group-append button");

        if (!input || !button) {
            return;
        }

        var wrapper = widget.parentNode;
        var feedback = wrapper.querySelector(".course-search-feedback");

        if (!feedback) {
            feedback = document.createElement("div");
            feedback.className = "course-search-feedback text-white small mt-2";
            feedback.setAttribute("role", "status");
            feedback.setAttribute("aria-live", "polite");
            wrapper.appendChild(feedback);
        }

        function resetFeedback() {
            feedback.textContent = "";
        }

        function showNoMatch(query) {
            feedback.textContent = 'No course found for "' + query +
                '". Try "computer", "science", "education", or "school".';
        }

        function showMultipleMatches(matches, query) {
            feedback.textContent = 'Multiple courses match "' + query + '": ';

            matches.forEach(function (course, index) {
                if (index > 0) {
                    feedback.appendChild(document.createTextNode(" or "));
                }

                var link = document.createElement("a");
                link.href = course.url;
                link.className = "text-white font-weight-bold";
                link.textContent = course.title;
                feedback.appendChild(link);
            });

            feedback.appendChild(document.createTextNode("."));
        }

        function submit() {
            var query = input.value.trim();
            resetFeedback();

            if (!query) {
                feedback.textContent = "Enter a keyword to search for a course.";
                input.focus();
                return;
            }

            var matches = findMatches(query);

            if (!matches.length) {
                showNoMatch(query);
                input.focus();
                input.select();
                return;
            }

            if (matches.length === 1) {
                window.location.href = matches[0].url;
                return;
            }

            showMultipleMatches(matches, query);
        }

        button.addEventListener("click", submit);

        input.addEventListener("keydown", function (event) {
            if (event.key === "Enter" || event.keyCode === 13) {
                event.preventDefault();
                submit();
            }
        });

        input.addEventListener("input", resetFeedback);
    }

    function init() {
        var widgets = document.querySelectorAll("[data-course-search]");
        Array.prototype.forEach.call(widgets, initSearchWidget);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
