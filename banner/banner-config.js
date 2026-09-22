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
    enabled: false,

    // Automatically open popup when index.html loads
    autoOpen: true,

    // Automatically transition to the next banner
    slideshow: true,

    // Time between slides in milliseconds (e.g., 5000 = 5 seconds)
    slideshowInterval: 5000,

    // Shows a "Don't show again today" button in the banner. When clicked, the auto-open
    // popup is suppressed until the next calendar day using localStorage (survives tab
    // switches and browser restarts, so newly added media can NOT re-trigger it today).
    rememberClosed: true,

    // Auto-detect files using server-side PHP (if your hosting supports PHP)
    // If enabled and get_banners.php is found, it will automatically scan banner/banner_img/
    autoDetectPhp: true,

    // Last updated timestamp (ms) - changes whenever admin edits/adds media or saves
    lastUpdated: 1790088528764
};

// Media Items to Display
const bannerMeta = {
    "banner/banner_img/2083_05_26_ECA_Program_IMG_1.jpeg": {"title": "ECA_Program_Pic_1 held on 2083/05/26"},
    "banner/banner_img/1000109365.jpg": {"title": "CTEVT-परीक्षा - 2083 (R & B) सञ्चालन सम्बन्धी अत्यन्त जरुरी सूचना"},
    "banner/banner_img/2083_05_26_ECA_Program_IMG_2.jpeg": {"title": "ECA_Program_Pic_2"},
    "banner/banner_img/2083_05_26_ECA_Program_IMG_4.jpeg": {"title": "ECA_Program_Pic_2 held on 2083/05/26"},
    "banner/banner_img/20260909_155614.jpg": {"title": "Samir_Tamang_Sir_Photo"},
    "banner/banner_img/page-header.jpg": {"title": "Drone View of Dandakharka"},
    "banner/banner_img/courses-1.jpg": {"title": "CTEVT-DCOM-Computer Lab (Students Performing Practical)"},
    "banner/banner_img/6th-sem.png": {"title": "CTEVT_DCOM_6th_SEM_Final_Exam_Updated_Routine_&_Center"},
    "banner/banner_img/CTEVT_2nd_4th_SEM_Exam_Notice.png": {"title": "CTEVT_DCOM_2nd_4th_Sem_Final_Exam_Notice"},
    "banner/banner_img/1000109735.jpg": {"title": "ECA_Program_2082-06-02_Pic_1"},
    "banner/banner_img/1000109736.jpg": {"title": "ECA_Program_2082-06-02_Pic_2"},
    "banner/banner_img/1000109732.jpg": {"title": "ECA_Program_2082-06-02_Pic_3"}
};

const bannerMedia = [
    "banner/banner_img/6th-sem.png",
    "banner/banner_img/CTEVT_2nd_4th_SEM_Exam_Notice.png",
    "banner/banner_img/1000109735.jpg",
    "banner/banner_img/1000109736.jpg",
    "banner/banner_img/1000109732.jpg"
];
