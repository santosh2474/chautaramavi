document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const galleryContainer = document.getElementById('gallery-container');
  const searchInput = document.getElementById('search-input');
  const searchClearBtn = document.getElementById('search-clear');
  const dateFromInput = document.getElementById('date-from');
  const dateToInput = document.getElementById('date-to');
  const dateClearBtn = document.getElementById('date-clear-btn');
  const totalCategoriesEl = document.getElementById('total-categories');
  const totalImagesEl = document.getElementById('total-images');
  const emptyStateEl = document.getElementById('empty-state');
  const emptyTitleEl = document.getElementById('empty-title');
  const emptyMessageEl = document.getElementById('empty-message');
  const categoryTabsContainer = document.getElementById('category-tabs');
  const tabCountAllEl = document.getElementById('tab-count-all');

  // Theme Toggle Elements
  const themeToggleBtn = document.getElementById('theme-toggle');
  const themeIconEl = document.getElementById('theme-icon');
  const themeLabelEl = document.getElementById('theme-label');

  // Modal Elements
  const modal = document.getElementById('image-modal');
  const modalClose = document.getElementById('modal-close');
  const modalImg = document.getElementById('modal-img');
  const modalCategory = document.getElementById('modal-category');
  const modalDate = document.getElementById('modal-date');
  const modalFilename = document.getElementById('modal-filename');
  const modalDownloadBtn = document.getElementById('modal-download-btn');
  const modalCounter = document.getElementById('modal-counter');
  const modalFullscreenBtn = document.getElementById('modal-fullscreen-btn');
  const modalPrevBtn = document.getElementById('modal-prev-btn');
  const modalNextBtn = document.getElementById('modal-next-btn');

  let allCategories = [];
  let currentActiveTab = 'all';
  let activeGalleryImages = [];
  let currentModalIndex = 0;

  // -------------------------------------------------------------
  // 1. Dark / Light Theme Manager
  // -------------------------------------------------------------
  function getPreferredTheme() {
    try {
      const savedTheme = localStorage.getItem('theme');
      if (savedTheme === 'dark' || savedTheme === 'light') {
        return savedTheme;
      }
    } catch (e) {
      // Gracefully handle restricted sandboxes
    }
    
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    if (theme === 'dark') {
      if (themeIconEl) themeIconEl.textContent = '☀️';
      if (themeLabelEl) themeLabelEl.textContent = 'Light';
      if (themeToggleBtn) themeToggleBtn.setAttribute('title', 'Switch to Light Mode');
    } else {
      if (themeIconEl) themeIconEl.textContent = '🌙';
      if (themeLabelEl) themeLabelEl.textContent = 'Dark';
      if (themeToggleBtn) themeToggleBtn.setAttribute('title', 'Switch to Dark Mode');
    }

    try {
      localStorage.setItem('theme', theme);
    } catch (e) {}
  }

  function initTheme() {
    const currentTheme = getPreferredTheme();
    applyTheme(currentTheme);

    if (themeToggleBtn) {
      themeToggleBtn.addEventListener('click', () => {
        const activeTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = activeTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
      });
    }
  }

  // -------------------------------------------------------------
  // 2. Category Metadata & Icons
  // -------------------------------------------------------------
  const categoryIcons = {
    nature: { icon: '🌿', nepali: 'प्रकृति तथा परिसर' },
    architecture: { icon: '🏛️', nepali: 'भवन तथा पूर्वाधार' },
    wallpapers: { icon: '🖼️', nepali: 'वालपेपर तथा तस्बिरहरू' },
    events: { icon: '🎉', nepali: 'कार्यक्रम तथा उत्सव' },
    sports: { icon: '⚽', nepali: 'खेलकुद' },
    academics: { icon: '📚', nepali: 'शैक्षिक गतिविधि' },
    awards: { icon: '🏆', nepali: 'पुरस्कार तथा सम्मान' },
    default: { icon: '📁', nepali: 'तस्बिर सङ्ग्रह' }
  };

  function getCategoryMeta(catName) {
    const key = catName.toLowerCase();
    for (const [k, meta] of Object.entries(categoryIcons)) {
      if (key.includes(k)) return meta;
    }
    return categoryIcons.default;
  }

  // -------------------------------------------------------------
  // 3. Load Gallery Data (file:// standalone + http fallback)
  // -------------------------------------------------------------
  async function loadGalleryData() {
    // 1. Standalone file:// execution using categories-data.js
    if (typeof window.GALLERY_DATA !== 'undefined' && Array.isArray(window.GALLERY_DATA) && window.GALLERY_DATA.length > 0) {
      allCategories = window.GALLERY_DATA;
      initializeGallery(allCategories);

      // If running over HTTP/HTTPS, attempt live background sync
      if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
        try {
          const response = await fetch('categories.json?t=' + Date.now());
          if (response.ok) {
            allCategories = await response.json();
            initializeGallery(allCategories);
          }
        } catch (e) {
          // Graceful fallback to embedded window.GALLERY_DATA
        }
      }
      return;
    }

    // 2. Fetch from categories.json (for web server environments)
    try {
      const response = await fetch('categories.json?t=' + Date.now());
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      allCategories = await response.json();
      initializeGallery(allCategories);
    } catch (error) {
      console.warn('Failed to load categories:', error);
      if (typeof window.GALLERY_DATA !== 'undefined' && Array.isArray(window.GALLERY_DATA)) {
        allCategories = window.GALLERY_DATA;
        initializeGallery(allCategories);
      } else {
        showErrorState(
          'No Categories or Photos Found',
          'Please launch <code>admin_app.py</code> to create albums and upload images.'
        );
      }
    }
  }

  // Initialize Gallery UI and Dynamic Tabs
  function initializeGallery(categories) {
    buildCategoryTabs(categories);
    applyFilterAndRender();
  }

  // Build Dynamic Category Filter Tabs
  function buildCategoryTabs(categories) {
    let totalAllImages = 0;
    
    // Clear dynamic tabs (preserve 'All' button)
    categoryTabsContainer.innerHTML = `
      <button class="tab-btn active" data-category="all">
        <span class="tab-icon">🌟</span>
        <span>All Albums</span>
        <span class="tab-count" id="tab-count-all">0</span>
      </button>
    `;

    categories.forEach(cat => {
      const imgCount = (cat.images || []).length;
      totalAllImages += imgCount;

      if (imgCount > 0) {
        const meta = getCategoryMeta(cat.category);
        const btn = document.createElement('button');
        btn.className = 'tab-btn';
        btn.dataset.category = cat.category.toLowerCase();
        btn.innerHTML = `
          <span class="tab-icon">${meta.icon}</span>
          <span>${escapeHTML(cat.category)}</span>
          <span class="tab-count">${imgCount}</span>
        `;
        btn.addEventListener('click', () => handleTabClick(cat.category.toLowerCase()));
        categoryTabsContainer.appendChild(btn);
      }
    });

    const allCountEl = document.getElementById('tab-count-all');
    if (allCountEl) allCountEl.textContent = totalAllImages;

    // Attach listener to 'All' button
    const allBtn = categoryTabsContainer.querySelector('[data-category="all"]');
    if (allBtn) {
      allBtn.addEventListener('click', () => handleTabClick('all'));
    }
  }

  function handleTabClick(categoryKey) {
    currentActiveTab = categoryKey;

    // Update active tab styling
    document.querySelectorAll('.tab-btn').forEach(btn => {
      if (btn.dataset.category === categoryKey) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    applyFilterAndRender();
  }

  // Normalize date strings into standard YYYY/MM/DD
  function normalizeDate(dateStr) {
    if (!dateStr) return '';
    return dateStr.trim().replace(/[-.]/g, '/');
  }

  // -------------------------------------------------------------
  // 4. Filter & Render Gallery (Keywords + Category + Date Range)
  // -------------------------------------------------------------
  function applyFilterAndRender() {
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const dateFromRaw = dateFromInput ? dateFromInput.value.trim() : '';
    const dateToRaw = dateToInput ? dateToInput.value.trim() : '';

    const dateFrom = normalizeDate(dateFromRaw);
    const dateTo = normalizeDate(dateToRaw);

    // Toggle search clear button
    if (query) {
      if (searchClearBtn) searchClearBtn.classList.remove('hidden');
    } else {
      if (searchClearBtn) searchClearBtn.classList.add('hidden');
    }

    // Toggle date reset button
    if (dateFromRaw || dateToRaw) {
      if (dateClearBtn) dateClearBtn.classList.remove('hidden');
    } else {
      if (dateClearBtn) dateClearBtn.classList.add('hidden');
    }

    let filtered = allCategories.map(cat => {
      const catNameLower = cat.category.toLowerCase();

      // Check tab filter
      if (currentActiveTab !== 'all' && catNameLower !== currentActiveTab) {
        return null;
      }

      let images = cat.images || [];

      // Filter images inside category
      images = images.filter(imgItem => {
        const filename = typeof imgItem === 'string' ? imgItem : (imgItem.name || '');
        const imgDate = typeof imgItem === 'object' && imgItem.date ? imgItem.date : '';
        const normImgDate = normalizeDate(imgDate);

        // 1. Keyword search (matches filename, category name, or date)
        if (query) {
          const matchQuery = filename.toLowerCase().includes(query) || 
                             catNameLower.includes(query) || 
                             (imgDate && imgDate.toLowerCase().includes(query)) ||
                             (normImgDate && normImgDate.includes(query));
          if (!matchQuery) return false;
        }

        // 2. Date Range Filter (From Date - To Date)
        if (dateFrom && normImgDate) {
          if (normImgDate < dateFrom) return false;
        }
        if (dateTo && normImgDate) {
          if (normImgDate > dateTo) return false;
        }

        // If a date filter is active and image has no date, exclude it
        if ((dateFrom || dateTo) && !normImgDate) {
          return false;
        }

        return true;
      });

      if (images.length === 0) return null;

      return {
        category: cat.category,
        images: images
      };
    }).filter(Boolean);

    renderGallery(filtered);
  }

  // Render Category Cards & Image Grid
  function renderGallery(categories) {
    galleryContainer.innerHTML = '';
    activeGalleryImages = [];

    let visibleCategoriesCount = 0;
    let totalImagesCount = 0;

    categories.forEach(catItem => {
      const categoryName = catItem.category;
      const images = catItem.images || [];

      if (images.length === 0) return;

      visibleCategoriesCount++;
      totalImagesCount += images.length;

      const meta = getCategoryMeta(categoryName);

      // Category Card Element with Glass Panel
      const card = document.createElement('div');
      card.className = 'category-card glass-panel';
      card.dataset.category = categoryName.toLowerCase();

      // Card Header
      const header = document.createElement('div');
      header.className = 'category-header';
      header.innerHTML = `
        <div class="category-title-wrap">
          <span class="category-icon glass-card">${meta.icon}</span>
          <div>
            <h2 class="category-title">${escapeHTML(categoryName)}</h2>
            <small style="color: var(--text-muted); font-size: 0.78rem; font-weight: 500;">${meta.nepali}</small>
          </div>
        </div>
        <span class="count-badge glass-pill">${images.length} ${images.length === 1 ? 'Photo' : 'Photos'}</span>
      `;

      // Image Grid
      const grid = document.createElement('div');
      grid.className = 'image-grid';

      images.forEach(imgItem => {
        const filename = typeof imgItem === 'string' ? imgItem : (imgItem.name || '');
        const imgDate = typeof imgItem === 'object' && imgItem.date ? imgItem.date : '';
        const filePath = `categories/${encodeURIComponent(categoryName)}/${encodeURIComponent(filename)}`;

        const imageIndex = activeGalleryImages.length;
        activeGalleryImages.push({
          filePath,
          categoryName,
          filename,
          imgDate
        });

        const item = document.createElement('div');
        item.className = 'image-item glass-card';
        item.dataset.filename = filename.toLowerCase();
        item.dataset.date = imgDate;

        item.innerHTML = `
          <div class="image-preview-box" data-image-index="${imageIndex}">
            <img src="${filePath}" alt="${escapeHTML(filename)}" loading="lazy" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100\\' height=\\'100\\'><text x=\\'50%\\' y=\\'50%\\' dominant-baseline=\\'middle\\' text-anchor=\\'middle\\' fill=\\'%23999\\'>Image Error</text></svg>';">
            <div class="preview-overlay">
              <span class="preview-icon">👁️ Full View</span>
            </div>
            ${imgDate ? `<span class="image-date-chip glass-pill">📅 ${escapeHTML(imgDate)}</span>` : ''}
          </div>
          <div class="image-details glass-surface">
            <div class="image-meta-wrap">
              <span class="image-filename" title="${escapeHTML(filename)}">${escapeHTML(filename)}</span>
              ${imgDate ? `<span class="image-date-sub"><span class="cal-mini-icon">📅</span> ${escapeHTML(imgDate)}</span>` : ''}
            </div>
            <a href="${filePath}" download="${escapeHTML(filename)}" class="btn btn-download glass-btn" title="Download Image">
              📥 Save
            </a>
          </div>
        `;

        grid.appendChild(item);
      });

      card.appendChild(header);
      card.appendChild(grid);
      galleryContainer.appendChild(card);
    });

    // Update Stats
    totalCategoriesEl.textContent = visibleCategoriesCount;
    totalImagesEl.textContent = totalImagesCount;

    // Toggle Empty State
    if (visibleCategoriesCount === 0) {
      showErrorState(
        'No Photographs Found',
        'No photos matched your current filter or search criteria. Try adjusting your keyword or date range.'
      );
    } else {
      emptyStateEl.classList.add('hidden');
    }

    // Attach Preview Event Listeners
    document.querySelectorAll('.image-preview-box').forEach(box => {
      box.addEventListener('click', () => {
        const idx = parseInt(box.dataset.imageIndex, 10);
        if (!isNaN(idx)) {
          openModal(idx);
        }
      });
    });
  }

  // -------------------------------------------------------------
  // 5. Input Event Listeners
  // -------------------------------------------------------------
  // Search input handler
  if (searchInput) {
    searchInput.addEventListener('input', applyFilterAndRender);
  }

  // Search clear button handler
  if (searchClearBtn) {
    searchClearBtn.addEventListener('click', () => {
      searchInput.value = '';
      applyFilterAndRender();
      searchInput.focus();
    });
  }

  // Date range inputs with input formatting helper
  function setupDateInput(inputEl) {
    if (!inputEl) return;
    inputEl.addEventListener('input', (e) => {
      applyFilterAndRender();
    });
  }

  setupDateInput(dateFromInput);
  setupDateInput(dateToInput);

  // Date clear button handler
  if (dateClearBtn) {
    dateClearBtn.addEventListener('click', () => {
      if (dateFromInput) dateFromInput.value = '';
      if (dateToInput) dateToInput.value = '';
      applyFilterAndRender();
    });
  }

  // -------------------------------------------------------------
  // 6. Lightbox Modal Handlers (Fullscreen, Arrow Keys, Mouse & Touch Sliding)
  // -------------------------------------------------------------
  function openModal(index) {
    if (!activeGalleryImages || activeGalleryImages.length === 0) return;
    currentModalIndex = Math.max(0, Math.min(index, activeGalleryImages.length - 1));

    renderModalImage();
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function renderModalImage(animationClass = '') {
    const imgObj = activeGalleryImages[currentModalIndex];
    if (!imgObj) return;

    modalImg.src = imgObj.filePath;
    modalCategory.textContent = imgObj.categoryName;
    modalFilename.textContent = imgObj.filename;

    if (modalCounter) {
      modalCounter.textContent = `${currentModalIndex + 1} / ${activeGalleryImages.length}`;
    }

    if (modalDate) {
      if (imgObj.imgDate) {
        modalDate.textContent = `📅 Uploaded: ${imgObj.imgDate}`;
        modalDate.classList.remove('hidden');
      } else {
        modalDate.classList.add('hidden');
      }
    }

    if (modalDownloadBtn) {
      modalDownloadBtn.setAttribute('href', imgObj.filePath);
      modalDownloadBtn.setAttribute('download', imgObj.filename);
    }

    // Animation
    modalImg.className = '';
    if (animationClass) {
      modalImg.classList.add(animationClass);
    }

    preloadAdjacentImages();
  }

  function showNextModalImage() {
    if (activeGalleryImages.length <= 1) return;
    currentModalIndex = (currentModalIndex + 1) % activeGalleryImages.length;
    renderModalImage('slide-from-right');
  }

  function showPrevModalImage() {
    if (activeGalleryImages.length <= 1) return;
    currentModalIndex = (currentModalIndex - 1 + activeGalleryImages.length) % activeGalleryImages.length;
    renderModalImage('slide-from-left');
  }

  function preloadAdjacentImages() {
    if (activeGalleryImages.length <= 1) return;
    const nextIdx = (currentModalIndex + 1) % activeGalleryImages.length;
    const prevIdx = (currentModalIndex - 1 + activeGalleryImages.length) % activeGalleryImages.length;
    const i1 = new Image();
    i1.src = activeGalleryImages[nextIdx].filePath;
    const i2 = new Image();
    i2.src = activeGalleryImages[prevIdx].filePath;
  }

  function isModalInFullscreen() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement || modal.classList.contains('mobile-force-landscape'));
  }

  function closeModal() {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    modalImg.src = '';
    document.body.style.overflow = '';

    // Unlock device orientation if locked
    try {
      if (screen.orientation && screen.orientation.unlock) {
        screen.orientation.unlock();
      } else if (screen.unlockOrientation) {
        screen.unlockOrientation();
      } else if (screen.webkitUnlockOrientation) {
        screen.webkitUnlockOrientation();
      }
    } catch (err) {}

    modal.classList.remove('mobile-force-landscape');

    if (document.fullscreenElement || document.webkitFullscreenElement) {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen().catch(() => {});
      }
    }

    updateFullscreenUI();
  }

  // --- Fullscreen Toggle Option (with Auto Mobile Landscape Rotation) ---
  async function toggleModalFullscreen() {
    const isFs = isModalInFullscreen();

    if (!isFs) {
      // 1. Enter Native Fullscreen
      let nativeFsSuccess = false;
      try {
        if (modal.requestFullscreen) {
          await modal.requestFullscreen();
          nativeFsSuccess = true;
        } else if (modal.webkitRequestFullscreen) {
          await modal.webkitRequestFullscreen();
          nativeFsSuccess = true;
        }
      } catch (e) {
        console.log('Native requestFullscreen note:', e);
      }

      // 2. Automatically Convert/Lock to Landscape on Mobile
      let orientationLocked = false;
      try {
        if (screen.orientation && screen.orientation.lock) {
          await screen.orientation.lock('landscape');
          orientationLocked = true;
        } else if (screen.lockOrientation) {
          orientationLocked = screen.lockOrientation('landscape');
        } else if (screen.webkitLockOrientation) {
          orientationLocked = screen.webkitLockOrientation('landscape');
        } else if (screen.mozLockOrientation) {
          orientationLocked = screen.mozLockOrientation('landscape');
        }
      } catch (err) {
        console.log('Orientation lock note:', err);
      }

      // 3. Fallback for iOS / mobile browsers where screen.orientation.lock is restricted:
      // If mobile screen is in portrait (height > width):
      if (!orientationLocked && window.innerHeight > window.innerWidth && window.innerWidth <= 850) {
        modal.classList.add('mobile-force-landscape');
      }

      updateFullscreenUI();
    } else {
      // Exit Fullscreen and Unlock Orientation
      try {
        if (screen.orientation && screen.orientation.unlock) {
          screen.orientation.unlock();
        } else if (screen.unlockOrientation) {
          screen.unlockOrientation();
        } else if (screen.webkitUnlockOrientation) {
          screen.webkitUnlockOrientation();
        }
      } catch (err) {}

      modal.classList.remove('mobile-force-landscape');

      if (document.fullscreenElement || document.webkitFullscreenElement) {
        if (document.exitFullscreen) {
          await document.exitFullscreen().catch(() => {});
        } else if (document.webkitExitFullscreen) {
          await document.webkitExitFullscreen().catch(() => {});
        }
      }

      updateFullscreenUI();
    }
  }

  function updateFullscreenUI() {
    const isFs = isModalInFullscreen();
    if (modalFullscreenBtn) {
      const expandIcon = modalFullscreenBtn.querySelector('.icon-expand');
      const compressIcon = modalFullscreenBtn.querySelector('.icon-compress');
      const fsText = modalFullscreenBtn.querySelector('.fs-text');

      if (isFs) {
        if (expandIcon) expandIcon.classList.add('hidden');
        if (compressIcon) compressIcon.classList.remove('hidden');
        if (fsText) fsText.textContent = 'Exit Fullscreen';
      } else {
        if (expandIcon) expandIcon.classList.remove('hidden');
        if (compressIcon) compressIcon.classList.add('hidden');
        if (fsText) fsText.textContent = 'Fullscreen';
      }
    }
  }

  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
      try {
        if (screen.orientation && screen.orientation.unlock) {
          screen.orientation.unlock();
        }
      } catch (e) {}
      modal.classList.remove('mobile-force-landscape');
    }
    updateFullscreenUI();
  });

  document.addEventListener('webkitfullscreenchange', () => {
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
      try {
        if (screen.orientation && screen.orientation.unlock) {
          screen.orientation.unlock();
        }
      } catch (e) {}
      modal.classList.remove('mobile-force-landscape');
    }
    updateFullscreenUI();
  });

  // Handle device orientation change or window resize
  window.addEventListener('orientationchange', () => {
    if (window.innerWidth > window.innerHeight) {
      modal.classList.remove('mobile-force-landscape');
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > window.innerHeight && modal.classList.contains('mobile-force-landscape')) {
      modal.classList.remove('mobile-force-landscape');
    }
  });

  // --- Mouse Click Listeners ---
  if (modalClose) modalClose.addEventListener('click', closeModal);
  if (modalFullscreenBtn) modalFullscreenBtn.addEventListener('click', (e) => { e.stopPropagation(); toggleModalFullscreen(); });
  if (modalPrevBtn) modalPrevBtn.addEventListener('click', (e) => { e.stopPropagation(); showPrevModalImage(); });
  if (modalNextBtn) modalNextBtn.addEventListener('click', (e) => { e.stopPropagation(); showNextModalImage(); });

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  // --- Keyboard Navigation (Arrow Keys, ESC, F) ---
  document.addEventListener('keydown', (e) => {
    if (modal.classList.contains('hidden')) return;

    if (e.key === 'Escape') {
      closeModal();
    } else if (e.key === 'ArrowRight' || e.key === 'Right') {
      e.preventDefault();
      showNextModalImage();
    } else if (e.key === 'ArrowLeft' || e.key === 'Left') {
      e.preventDefault();
      showPrevModalImage();
    } else if (e.key === 'f' || e.key === 'F') {
      e.preventDefault();
      toggleModalFullscreen();
    }
  });

  // --- Mobile Touch Sliding (Swipe Left/Right in Portrait & Landscape) ---
  let touchStartX = 0;
  let touchStartY = 0;
  let touchStartTime = 0;

  modal.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      touchStartTime = performance.now();
    }
  }, { passive: true });

  modal.addEventListener('touchend', (e) => {
    if (e.changedTouches.length === 1) {
      const deltaX = e.changedTouches[0].clientX - touchStartX;
      const deltaY = e.changedTouches[0].clientY - touchStartY;
      const duration = performance.now() - touchStartTime;

      const isForceLandscape = modal.classList.contains('mobile-force-landscape');

      if (isForceLandscape) {
        // When CSS rotated 90deg, visual X axis aligns with physical Y axis:
        if (Math.abs(deltaY) > 40 && Math.abs(deltaX) < 90 && duration < 500) {
          if (deltaY < 0) {
            showNextModalImage(); // Swiped visually left -> Next
          } else {
            showPrevModalImage(); // Swiped visually right -> Prev
          }
        }
      } else {
        // Native orientation or locked landscape:
        if (Math.abs(deltaX) > 40 && Math.abs(deltaY) < 80 && duration < 500) {
          if (deltaX < 0) {
            showNextModalImage(); // Swiped left -> Next
          } else {
            showPrevModalImage(); // Swiped right -> Previous
          }
        }
      }
    }
  }, { passive: true });

  function showErrorState(title, message) {
    emptyTitleEl.textContent = title;
    emptyMessageEl.innerHTML = message;
    emptyStateEl.classList.remove('hidden');
  }

  function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
      tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
  }

  // Start Theme Initialization and Gallery Data Load
  initTheme();
  loadGalleryData();
});
