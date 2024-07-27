let nextBtn = document.querySelector("#next");
let prevBtn = document.querySelector("#prev");
let closeBtn = document.querySelector("#close");
let slides = document.querySelectorAll(".slide");
let changeSlide = 0;
let autoSlideInterval;
let isAutoSlideStopped = false;
let isMouseHovering = false;

function showSlide(index) {
    slides.forEach((slide, idx) => {
        if (idx === index) {
            slide.classList.add("show");
        } else {
            slide.classList.remove("show");
            let video = slide.querySelector("video");
            if (video) {
                video.pause();
                video.currentTime = 0;
            }
        }
    });
}

function nextSlide() {
    changeSlide = (changeSlide + 1) % slides.length;
    showSlide(changeSlide);
}

// Start automatic sliding
function startAutoSlide() {
    if (!isAutoSlideStopped && !isMouseHovering) {
        autoSlideInterval = setInterval(nextSlide, 5000); // Move slides every 5 seconds
    }
}

// Stop automatic sliding
function stopAutoSlide() {
    isAutoSlideStopped = true;
    clearInterval(autoSlideInterval);
}

// Check if any video is playing
function isAnyVideoPlaying() {
    return Array.from(document.querySelectorAll("#slideContainer video")).some(video => !video.paused);
}

// Add event listeners to all videos to stop auto sliding when playing
document.querySelectorAll("#slideContainer video").forEach(video => {
    video.addEventListener("play", () => {
        stopAutoSlide();
    });
    video.addEventListener("pause", () => {
        isAutoSlideStopped = false;
        if (!isAnyVideoPlaying() && !isMouseHovering) {
            startAutoSlide();
        }
    });
    video.addEventListener("ended", () => {
        isAutoSlideStopped = false;
        if (!isAnyVideoPlaying() && !isMouseHovering) {
            startAutoSlide();
        }
    });
});

// Event listeners for slide navigation buttons
nextBtn.addEventListener("click", function() {
    stopAutoSlide(); // Stop automatic sliding when the user clicks next
    nextSlide();
    startAutoSlide(); // Restart automatic sliding after user interaction
});

prevBtn.addEventListener('click', function () {
    stopAutoSlide(); // Stop automatic sliding when the user clicks previous
    changeSlide = (changeSlide - 1 + slides.length) % slides.length;
    showSlide(changeSlide);
    startAutoSlide(); // Restart automatic sliding after user interaction
});

closeBtn.addEventListener('click', function() {
    document.getElementById("slideContainer").style.display = "none";
    
    // Pause all videos when the banner is closed
    document.querySelectorAll("#slideContainer video").forEach(video => {
        video.pause();
        video.currentTime = 0;
    });

    stopAutoSlide(); // Stop automatic sliding when the banner is closed
});

// Add event listeners to stop and restart auto sliding on hover
document.querySelectorAll("#slideContainer img, #slideContainer video").forEach(media => {
    media.addEventListener("mouseenter", () => {
        isMouseHovering = true;
        stopAutoSlide();
    });
    media.addEventListener("mouseleave", () => {
        isMouseHovering = false;
        isAutoSlideStopped = false;
        if (!isAnyVideoPlaying()) {
            startAutoSlide();
        }
    });
});

// Initialize
showSlide(changeSlide);
startAutoSlide(); // Start automatic sliding on page load