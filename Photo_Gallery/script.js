document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const galleryContainer = document.getElementById('gallery-container');
  const searchInput = document.getElementById('search-input');
  const searchClearBtn = document.getElementById('search-clear');
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
  const modalFilename = document.getElementById('modal-filename');
  const modalDownloadBtn = document.getElementById('modal-download-btn');

  let allCategories = [];
  let currentActiveTab = 'all';

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
    
    // Default to system preference if available
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

  // Filter & Render Gallery
  function applyFilterAndRender() {
    const query = searchInput.value.trim().toLowerCase();

    // Toggle search clear button
    if (query) {
      searchClearBtn.classList.remove('hidden');
    } else {
      searchClearBtn.classList.add('hidden');
    }

    let filtered = allCategories.map(cat => {
      const catNameLower = cat.category.toLowerCase();

      // Check tab filter
      if (currentActiveTab !== 'all' && catNameLower !== currentActiveTab) {
        return null;
      }

      // Check search filter
      let images = cat.images || [];
      if (query) {
        const matchCategory = catNameLower.includes(query);
        images = images.filter(img => img.toLowerCase().includes(query) || matchCategory);
      }

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

      images.forEach(filename => {
        const filePath = `categories/${encodeURIComponent(categoryName)}/${encodeURIComponent(filename)}`;

        const item = document.createElement('div');
        item.className = 'image-item glass-card';
        item.dataset.filename = filename.toLowerCase();

        item.innerHTML = `
          <div class="image-preview-box" data-filepath="${filePath}" data-category="${escapeHTML(categoryName)}" data-filename="${escapeHTML(filename)}">
            <img src="${filePath}" alt="${escapeHTML(filename)}" loading="lazy" onerror="this.onerror=null; this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'100\\' height=\\'100\\'><text x=\\'50%\\' y=\\'50%\\' dominant-baseline=\\'middle\\' text-anchor=\\'middle\\' fill=\\'%23999\\'>Image Error</text></svg>';">
            <div class="preview-overlay">
              <span class="preview-icon">👁️ Full View</span>
            </div>
          </div>
          <div class="image-details glass-surface">
            <span class="image-filename" title="${escapeHTML(filename)}">${escapeHTML(filename)}</span>
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
        'No photos matched your current filter or search criteria. Use <code>admin_app.py</code> to manage photos.'
      );
    } else {
      emptyStateEl.classList.add('hidden');
    }

    // Attach Preview Event Listeners
    document.querySelectorAll('.image-preview-box').forEach(box => {
      box.addEventListener('click', () => {
        const filePath = box.dataset.filepath;
        const catName = box.dataset.category;
        const fileName = box.dataset.filename;
        openModal(filePath, catName, fileName);
      });
    });
  }

  // Search input handler
  searchInput.addEventListener('input', applyFilterAndRender);

  // Search clear button handler
  searchClearBtn.addEventListener('click', () => {
    searchInput.value = '';
    applyFilterAndRender();
    searchInput.focus();
  });

  // Lightbox Modal Handlers
  function openModal(filePath, catName, fileName) {
    modalImg.src = filePath;
    modalCategory.textContent = catName;
    modalFilename.textContent = fileName;

    modalDownloadBtn.setAttribute('href', filePath);
    modalDownloadBtn.setAttribute('download', fileName);

    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    modalImg.src = '';
    document.body.style.overflow = '';
  }

  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
      closeModal();
    }
  });

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
