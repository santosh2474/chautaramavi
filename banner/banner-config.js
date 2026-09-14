/**
 * ==========================================================================
 * Shree Chautara Secondary School - Banner Configuration
 * Website: www.chautaramavi.edu.np
 * ==========================================================================
 * 
 * HOW TO ADD OR REMOVE BANNER MEDIA:
 * 1. Place your media file into the 'banner/banner_img/' folder.
 * 2. Add its relative path to the 'bannerMedia' array below.
 *    Example: "banner/banner_img/notice-admissions.pdf"
 * 3. To remove a file, simply delete or comment out its line from the array.
 * 
 * SUPPORTED FORMATS:
 * - Images:    .jpg, .jpeg, .png, .webp, .gif
 * - Documents: .pdf
 * - Videos:    .mp4, .webm, .ogg
 * ==========================================================================
 */

// General Banner Settings
const bannerSettings = {
    // Master switch: Enable or disable the entire banner media viewer feature on the website
    enabled: true,

    // Automatically open popup when index.html loads
    autoOpen: true,

    // Automatically transition to the next banner
    slideshow: true,

    // Time between slides in milliseconds (e.g., 5000 = 5 seconds)
    slideshowInterval: 5000,

    // If true, remembers when the user closes the banner for the current session (or 24 hours)
    rememberClosed: false,

    // Auto-detect files using server-side PHP (if your hosting supports PHP)
    // If enabled and get_banners.php is found, it will automatically scan banner/banner_img/
    autoDetectPhp: true
};

// Media Items to Display
const bannerMeta = {
    "banner/banner_img/2083_05_26_ECA_Program_IMG_1.jpeg": {"title": "ECA_Program_Pic_1"},
    "banner/banner_img/1000109365.jpg": {"title": "CTEVT परीक्षा - 2083 सञ्चालन सम्बन्धी अत्यन्त जरुरी सूचना"}
};

const bannerMedia = [
    "banner/banner_img/1000109365.jpg",
    "banner/banner_img/2083_05_26_ECA_Program_IMG_1.jpeg",
    "banner/banner_img/2083_05_26_ECA_Program_IMG_2.jpeg",
    "banner/banner_img/2083_05_26_ECA_Program_IMG_3.jpeg",
    "banner/banner_img/2083_05_26_ECA_Program_IMG_4.jpeg"
];
