/**
 * Crop Recommendation Application Frontend Logic
 * Handles session lifecycle, authentication, presets, live agronomic validation,
 * safe result rendering, theme switching, and local prediction history.
 */

/* ─── STATE ────────────────────────────────────────────────────────────── */
let csrfToken = '';
let currentUser = null;
let registering = false;
let currentPredictionInputs = null;

/** Allowlisted crop image filenames — only verified files in frontend/static */
const CROP_IMAGE_ALLOWLIST = {
  'apple.jpg': true,
  'banana.jpg': true,
  'blackgram.jpg': true,
  'chickpea.jpg': true,
  'coconut.jpg.jpeg': true,
  'coffee.jpg': true,
  'cotton.jpg': true,
  'grapes.jpg': true,
  'kidneybeans.jpg': true,
  'lentil.jpg': true,
  'maize.jpg': true,
  'mango.jpeg': true,
  'mungbean.jpg': true,
  'muskmelon.jpeg': true,
  'orange.jpeg': true,
  'papaya.jpeg': true,
  'pegionpeas.jpg': true,
  'pomegranate.jpg': true,
  'rice.jpeg': true,
  'watermelon.jpeg': true
};

/** Botanical classification dictionary for all 22 benchmark crops */
const CROP_CATEGORIES = {
  rice: 'Cereal Grain',
  maize: 'Cereal Grain',
  chickpea: 'Legume / Pulse',
  kidneybeans: 'Legume / Pulse',
  pigeonpeas: 'Legume / Pulse',
  mungbean: 'Legume / Pulse',
  blackgram: 'Legume / Pulse',
  lentil: 'Legume / Pulse',
  mothbeans: 'Legume / Pulse',
  apple: 'Fruit Crop',
  banana: 'Fruit Crop',
  grapes: 'Fruit Crop',
  mango: 'Fruit Crop',
  muskmelon: 'Fruit Crop',
  orange: 'Fruit Crop',
  papaya: 'Fruit Crop',
  pomegranate: 'Fruit Crop',
  watermelon: 'Fruit Crop',
  cotton: 'Commercial / Fiber',
  coffee: 'Plantation / Beverage',
  coconut: 'Plantation / Oil',
  jute: 'Commercial / Fiber'
};

/* ─── THEME TOGGLE (LIGHT / DARK MODE) ──────────────────────────────────── */
function initTheme() {
  const saved = localStorage.getItem('crop_theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  applyTheme(theme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('crop_theme', theme);
  const icons = document.querySelectorAll('.theme-icon, .theme-toggle-btn i, #themeIcon');
  icons.forEach(icon => {
    if (theme === 'dark') {
      icon.className = 'fa-solid fa-sun theme-icon';
    } else {
      icon.className = 'fa-solid fa-moon theme-icon';
    }
  });
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

/* ─── BACKGROUND SLIDESHOW ──────────────────────────────────────────────── */
(function setupSlideshow() {
  const slides = document.querySelectorAll('.bg-slideshow .slide');
  const dotsWrap = document.getElementById('slideDots');
  if (!slides.length || !dotsWrap) return;

  let current = 0;
  dotsWrap.replaceChildren();

  function goToSlide(index) {
    slides[current].classList.remove('active');
    const prevBtn = dotsWrap.children[current];
    if (prevBtn) {
      prevBtn.classList.remove('active');
      prevBtn.setAttribute('aria-current', 'false');
    }
    current = index;
    slides[current].classList.add('active');
    const nextBtn = dotsWrap.children[current];
    if (nextBtn) {
      nextBtn.classList.add('active');
      nextBtn.setAttribute('aria-current', 'true');
    }
  }

  slides.forEach((_, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'slide-dot-btn' + (i === 0 ? ' active' : '');
    btn.setAttribute('aria-label', `Show background slide ${i + 1} of ${slides.length}`);
    btn.setAttribute('aria-current', i === 0 ? 'true' : 'false');
    btn.addEventListener('click', () => goToSlide(i));
    dotsWrap.appendChild(btn);
  });

  const prefersReducedMotion = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!prefersReducedMotion) {
    setInterval(() => {
      goToSlide((current + 1) % slides.length);
    }, 6000);
  }
})();

/* ─── TOAST NOTIFICATIONS ───────────────────────────────────────────────── */
function showToast(msg, type = 'info') {
  const icons = {
    success: 'fa-circle-check',
    error: 'fa-circle-xmark',
    info: 'fa-circle-info'
  };
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `custom-toast ${type}`;
  toast.setAttribute('role', 'status');

  const icon = document.createElement('i');
  icon.className = `fa-solid ${icons[type] || icons.info}`;
  icon.setAttribute('aria-hidden', 'true');

  const span = document.createElement('span');
  span.textContent = msg;

  toast.append(icon, span);
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity .4s ease';
    setTimeout(() => toast.remove(), 450);
  }, 4000);
}

/* ─── VIEW NAVIGATION ───────────────────────────────────────────────────── */
function showView(id) {
  if (['predict', 'result'].includes(id) && !currentUser) {
    id = 'login';
  }

  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById(id);
  if (target) {
    target.classList.add('active');
  }

  if (id === 'login') {
    const loginErr = document.getElementById('loginError');
    if (loginErr && !loginErr.dataset.persistent) {
      loginErr.style.display = 'none';
    }
    updateRememberedUsersUI();
  }

  try {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (_) {
    window.scrollTo(0, 0);
  }
}

/* ─── AUTHENTICATION HELPERS ────────────────────────────────────────────── */
function togglePassword(visible) {
  ['loginPass', 'confirmPass'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.type = visible ? 'text' : 'password';
  });
}

function setAuthMode(isRegister) {
  if (registering === isRegister) return;
  toggleAuthMode();
}

function toggleAuthMode() {
  registering = !registering;
  const form = document.getElementById('authForm');
  if (form) form.reset();
  togglePassword(false);

  // Sync segmented buttons
  const tabSignIn = document.getElementById('tabSignIn');
  const tabRegister = document.getElementById('tabRegister');
  if (tabSignIn && tabRegister) {
    tabSignIn.classList.toggle('active', !registering);
    tabRegister.classList.toggle('active', registering);
  }

  const pwdMeter = document.getElementById('passwordMeter');
  if (pwdMeter) pwdMeter.style.display = registering ? 'block' : 'none';
  updatePasswordMeter('');

  document.getElementById('authTitle').textContent = registering ? 'Create Account' : 'Welcome Back';
  document.getElementById('authSubtitle').textContent = registering
    ? 'Save your account and explore crop recommendations'
    : 'Sign in to access crop predictions';
  document.getElementById('authSubmit').textContent = registering ? 'Create account' : 'Sign in';
  document.getElementById('authToggle').textContent = registering
    ? 'Already registered? Sign in'
    : 'New here? Create an account';

  const confirmGroup = document.getElementById('confirmGroup');
  const confirmPass = document.getElementById('confirmPass');
  confirmGroup.hidden = !registering;
  confirmPass.disabled = !registering;
  confirmPass.required = registering;

  document.getElementById('loginPass').autocomplete = registering ? 'new-password' : 'current-password';
  const loginErr = document.getElementById('loginError');
  if (loginErr) loginErr.style.display = 'none';
}

function updatePasswordMeter(password) {
  const fill = document.getElementById('passwordMeterFill');
  if (!fill) return;

  if (!password) {
    fill.style.width = '0%';
    return;
  }

  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 2) {
    fill.style.width = '33%';
    fill.style.backgroundColor = '#ef4444'; // Red (Weak)
  } else if (score <= 3) {
    fill.style.width = '66%';
    fill.style.backgroundColor = '#f59e0b'; // Amber (Fair)
  } else {
    fill.style.width = '100%';
    fill.style.backgroundColor = '#10b981'; // Emerald (Strong)
  }
}

/* ─── RESILIENT API REQUEST ─────────────────────────────────────────────── */
async function postJSON(url, body = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken
      },
      body: JSON.stringify(body),
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    let data;
    try {
      data = await response.json();
    } catch (_) {
      const statusMessages = {
        502: 'The backend service is unreachable. It may be starting up — please try again shortly.',
        503: 'The service is temporarily unavailable. Please try again in a moment.',
        429: 'Too many attempts. Please wait 15 minutes before trying again.',
      };
      throw new Error(statusMessages[response.status] || `Server returned an unexpected response (HTTP ${response.status}).`);
    }

    if (data && data.csrf_token) {
      csrfToken = data.csrf_token;
    }
    return { response, data };
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out. The server may be waking up from cold start — please retry.');
    }
    throw error;
  }
}

/* ─── LOGIN / REGISTRATION HANDLER ──────────────────────────────────────── */
async function handleLogin(event) {
  event.preventDefault();
  const button = document.getElementById('authSubmit');
  const toggle = document.getElementById('authToggle');
  const errorEl = document.getElementById('loginError');
  const errorText = document.getElementById('loginErrorText');

  button.disabled = true;
  toggle.disabled = true;
  if (errorEl) errorEl.style.display = 'none';

  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;
  const confirmPass = document.getElementById('confirmPass').value;

  try {
    const endpoint = registering ? '/api/register' : '/api/login';
    const payload = {
      username,
      password,
      confirm_password: confirmPass
    };

    const { data } = await postJSON(endpoint, payload);
    if (!data.success) {
      throw new Error(data.error || 'Authentication failed.');
    }

    currentUser = data.username;
    document.getElementById('authForm').reset();
    togglePassword(false);
    proceedToLogin(currentUser);
    showToast(`Welcome, ${currentUser}! 🌱`, 'success');
  } catch (error) {
    if (errorText) errorText.textContent = error.message || 'Could not sign in. Try again.';
    if (errorEl) errorEl.style.display = 'block';
  } finally {
    button.disabled = false;
    toggle.disabled = false;
  }
}

function proceedToLogin(username) {
  const navUser = document.getElementById('navUser');
  const navUser2 = document.getElementById('navUser2');
  if (navUser) navUser.textContent = username;
  if (navUser2) navUser2.textContent = username;
  saveRememberedProfile(username);
  updateNavActivityBadges();
  loadHistory();
  showView('predict');
}

/* ─── LOGOUT HANDLER ────────────────────────────────────────────────────── */
async function handleLogout() {
  closeProfileDrawer();
  try {
    const { data } = await postJSON('/api/logout');
    if (!data.success) throw new Error(data.error);
  } catch (error) {
    console.warn('Logout notice:', error);
  }

  currentUser = null;
  const authForm = document.getElementById('authForm');
  if (authForm) authForm.reset();

  const historyList = document.getElementById('historyList');
  if (historyList) historyList.replaceChildren();

  const historySection = document.getElementById('historySection');
  if (historySection) historySection.style.display = 'none';

  const cropName = document.getElementById('cropName');
  if (cropName) cropName.textContent = '';

  const cropWrap = document.getElementById('cropImageWrap');
  if (cropWrap) cropWrap.replaceChildren();

  const resultDetails = document.getElementById('resultDetails');
  if (resultDetails) resultDetails.replaceChildren();

  updateRememberedUsersUI();
  updateNavActivityBadges();
  showView('landing');
  showToast('Logged out successfully', 'info');
}

/* ─── QUICK PRESETS & LIVE CONTEXTUAL BADGES ────────────────────────────── */
const PRESETS = {
  rice: { Nitrogen: 90, Phosphorus: 42, Potassium: 43, Temperature: 20.5, Humidity: 82, Ph: 6.5, Rainfall: 200 },
  maize: { Nitrogen: 78, Phosphorus: 47, Potassium: 20, Temperature: 22.8, Humidity: 65, Ph: 6.2, Rainfall: 95 },
  coffee: { Nitrogen: 100, Phosphorus: 28, Potassium: 30, Temperature: 25.5, Humidity: 58, Ph: 6.8, Rainfall: 160 },
  grapes: { Nitrogen: 23, Phosphorus: 134, Potassium: 204, Temperature: 23.8, Humidity: 81, Ph: 6.0, Rainfall: 69 }
};

function applyPreset(name) {
  if (name === 'clear') {
    document.getElementById('predictForm').reset();
    updateAllLiveBadges();
    showToast('Form cleared', 'info');
    return;
  }

  const values = PRESETS[name];
  if (!values) return;

  for (const [key, val] of Object.entries(values)) {
    const input = document.querySelector(`[name="${key}"]`);
    if (input) input.value = val;
  }
  updateAllLiveBadges();
  showToast(`Loaded ${name.toUpperCase()} benchmark profile 🌱`, 'success');
}

function updateLiveBadge(field, val) {
  const v = parseFloat(val);
  const badge = document.getElementById(`badge-${field}`);
  if (!badge) return;

  if (isNaN(v)) {
    const defaults = {
      n: 'Ratio in Soil',
      p: 'Ratio in Soil',
      k: 'Ratio in Soil',
      ph: 'pH Scale',
      temp: 'Celsius',
      hum: '0–100%',
      rain: 'Precipitation'
    };
    badge.textContent = defaults[field] || '';
    return;
  }

  if (field === 'ph') {
    if (v < 5.5) badge.textContent = 'Acidic (Strong)';
    else if (v < 6.5) badge.textContent = 'Slightly Acidic';
    else if (v <= 7.5) badge.textContent = 'Optimal Neutral';
    else if (v <= 8.5) badge.textContent = 'Slightly Alkaline';
    else badge.textContent = 'Alkaline (Strong)';
  } else if (field === 'temp') {
    if (v < 15) badge.textContent = 'Cool (<15°C)';
    else if (v <= 28) badge.textContent = 'Moderate (15–28°C)';
    else badge.textContent = 'Warm / Tropical (>28°C)';
  } else if (field === 'hum') {
    if (v < 40) badge.textContent = 'Dry (<40%)';
    else if (v <= 70) badge.textContent = 'Comfortable (40–70%)';
    else badge.textContent = 'Humid (>70%)';
  } else if (field === 'rain') {
    if (v < 75) badge.textContent = 'Low (<75mm)';
    else if (v <= 175) badge.textContent = 'Moderate (75–175mm)';
    else badge.textContent = 'High (>175mm)';
  } else {
    badge.textContent = `Level: ${v}`;
  }
}

function updateAllLiveBadges() {
  const fields = [
    { id: 'n', name: 'Nitrogen' },
    { id: 'p', name: 'Phosphorus' },
    { id: 'k', name: 'Potassium' },
    { id: 'ph', name: 'Ph' },
    { id: 'temp', name: 'Temperature' },
    { id: 'hum', name: 'Humidity' },
    { id: 'rain', name: 'Rainfall' }
  ];

  fields.forEach(f => {
    const input = document.querySelector(`[name="${f.name}"]`);
    if (input) updateLiveBadge(f.id, input.value);
  });
}

/* ─── PREDICTION HANDLER ────────────────────────────────────────────────── */
async function handlePredict(e) {
  e.preventDefault();

  const btn = document.getElementById('btnPredict');
  const spinner = document.getElementById('spinner');
  const btnText = document.getElementById('btnText');

  btn.disabled = true;
  spinner.classList.add('show');
  btnText.textContent = 'Analyzing Soil & Weather…';

  const fd = new FormData(e.target);
  const body = {};
  fd.forEach((v, k) => { body[k] = v; });

  try {
    const { response, data } = await postJSON('/predict', body);

    // Early return for 401 session expiry (preserve form values)
    if (response.status === 401) {
      currentUser = null;
      showToast('Session expired. Please sign in again (soil inputs preserved).', 'error');
      showView('login');
      return;
    }

    if (data.success) {
      currentPredictionInputs = { ...body, crop: data.crop };
      renderResult(data, body);
      showToast(`Recommended: ${data.crop.toUpperCase()} 🌱`, 'success');
      saveHistory(body, data.crop);
      showView('result');
    } else {
      showToast(data.error || 'Prediction failed. Please review your inputs.', 'error');
    }
  } catch (err) {
    showToast(err.message || 'Server error — please try again.', 'error');
    console.error(err);
  } finally {
    btn.disabled = false;
    spinner.classList.remove('show');
    btnText.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i> Predict Suitable Crop';
  }
}

/* ─── SAFE RESULT RENDERING (DOM APIs & ALLOWLIST) ───────────────────────── */
function renderResult(data, inputs) {
  const crop = data.crop || 'Unknown Crop';
  const cropLower = crop.toLowerCase();

  // Crop Name
  const cropEl = document.getElementById('cropName');
  cropEl.textContent = crop;

  // Category Pill
  const categoryEl = document.getElementById('cropCategory');
  if (categoryEl) {
    categoryEl.textContent = CROP_CATEGORIES[cropLower] || 'Agricultural Crop';
  }

  // Safe image display
  const wrap = document.getElementById('cropImageWrap');
  wrap.replaceChildren();

  if (data.image && CROP_IMAGE_ALLOWLIST[data.image]) {
    const container = document.createElement('div');
    container.className = 'result-img-wrap';

    const img = document.createElement('img');
    img.src = '/static/' + data.image;
    img.alt = `Recommended crop: ${crop}`;
    img.className = 'img-fluid';
    img.loading = 'lazy';

    img.onerror = () => {
      wrap.replaceChildren();
      const fallback = document.createElement('p');
      fallback.className = 'no-img-msg';
      fallback.textContent = '📷 Crop image could not be loaded';
      wrap.appendChild(fallback);
    };

    container.appendChild(img);
    wrap.appendChild(container);
  } else {
    const p = document.createElement('p');
    p.className = 'no-img-msg';
    p.textContent = '📷 No image available for this crop variety';
    wrap.appendChild(p);
  }

  // Detail Chips (Safe DOM construction)
  const detailsEl = document.getElementById('resultDetails');
  detailsEl.replaceChildren();

  const chips = [
    { icon: 'fa-n', label: 'N', val: inputs.Nitrogen, unit: '' },
    { icon: 'fa-p', label: 'P', val: inputs.Phosphorus, unit: '' },
    { icon: 'fa-k', label: 'K', val: inputs.Potassium, unit: '' },
    { icon: 'fa-temperature-half', label: '', val: inputs.Temperature, unit: '°C' },
    { icon: 'fa-droplet', label: '', val: inputs.Humidity, unit: '%' },
    { icon: 'fa-vial', label: 'pH', val: inputs.Ph, unit: '' },
    { icon: 'fa-cloud-rain', label: '', val: inputs.Rainfall, unit: 'mm' }
  ];

  chips.forEach(chip => {
    const div = document.createElement('div');
    div.className = 'detail-chip';

    const icon = document.createElement('i');
    icon.className = `fa-solid ${chip.icon}`;
    icon.setAttribute('aria-hidden', 'true');

    const labelText = chip.label ? `${chip.label}: ` : '';
    const textNode = document.createTextNode(` ${labelText}${chip.val}${chip.unit}`);

    div.append(icon, textNode);
    detailsEl.appendChild(div);
  });
}

function copyResultSummary() {
  if (!currentPredictionInputs) return;
  const p = currentPredictionInputs;
  const summary = [
    `🌾 CROP RECOMMENDATION: ${p.crop.toUpperCase()}`,
    `• Soil: Nitrogen=${p.Nitrogen}, Phosphorus=${p.Phosphorus}, Potassium=${p.Potassium}, pH=${p.Ph}`,
    `• Climate: Temp=${p.Temperature}°C, Humidity=${p.Humidity}%, Rainfall=${p.Rainfall}mm`,
    `• Source: CropAdvisor AI ML Engine`
  ].join('\n');

  navigator.clipboard.writeText(summary).then(() => {
    showToast('Recommendation summary copied to clipboard! 📋', 'success');
  }).catch(() => {
    showToast('Could not copy summary.', 'info');
  });
}

/* ─── PREDICTION HISTORY (LOCAL-ONLY) ───────────────────────────────────── */
function getHistory() {
  if (!currentUser) return [];
  try {
    const raw = localStorage.getItem(`crop_history_${currentUser}`);
    const history = JSON.parse(raw || '[]');
    return Array.isArray(history)
      ? history.filter(x => x && typeof x === 'object').slice(0, 50)
      : [];
  } catch (_) {
    return [];
  }
}

function setHistory(arr) {
  if (!currentUser) return;
  try {
    localStorage.setItem(`crop_history_${currentUser}`, JSON.stringify(arr));
  } catch (_) {
    showToast('Prediction history could not be saved to this browser.', 'info');
  }
}

function saveHistory(inputs, crop) {
  const h = getHistory();
  h.unshift({
    crop,
    n: inputs.Nitrogen,
    p: inputs.Phosphorus,
    k: inputs.Potassium,
    temp: inputs.Temperature,
    hum: inputs.Humidity,
    ph: inputs.Ph,
    rain: inputs.Rainfall,
    time: new Date().toLocaleString()
  });
  if (h.length > 50) h.pop();
  setHistory(h);
  saveRememberedProfile(currentUser);
  updateNavActivityBadges();
  loadHistory();
}

function filterHistory(query) {
  const q = (query || '').toLowerCase().trim();
  const items = document.querySelectorAll('.history-item');
  let visibleCount = 0;
  items.forEach(el => {
    const text = el.textContent.toLowerCase();
    const match = text.includes(q);
    el.style.display = match ? 'flex' : 'none';
    if (match) visibleCount++;
  });

  const list = document.getElementById('historyList');
  let noMatch = document.getElementById('historyNoMatches');
  if (items.length > 0 && visibleCount === 0 && q) {
    if (!noMatch) {
      noMatch = document.createElement('div');
      noMatch.id = 'historyNoMatches';
      noMatch.className = 'text-center py-3 text-muted';
      noMatch.style.fontSize = '0.85rem';
      list?.appendChild(noMatch);
    }
    noMatch.textContent = `No saved predictions match "${query}".`;
    noMatch.style.display = 'block';
  } else if (noMatch) {
    noMatch.style.display = 'none';
  }
}

function loadHistory() {
  const h = getHistory();
  const sec = document.getElementById('historySection');
  const list = document.getElementById('historyList');
  if (!sec || !list) return;

  if (!h.length) {
    sec.style.display = 'none';
    return;
  }

  sec.style.display = 'block';
  list.replaceChildren();

  h.forEach(x => {
    const item = document.createElement('div');
    item.className = 'history-item';
    item.title = 'Click to load these soil values back into the prediction form';

    const desc = document.createElement('div');

    const crop = document.createElement('div');
    crop.className = 'crop';
    crop.textContent = `🌱 ${x.crop}`;

    const details = document.createElement('div');
    details.className = 'details';
    details.textContent = `N:${x.n} P:${x.p} K:${x.k} | ${x.temp}°C | ${x.hum}% | pH ${x.ph} | ${x.rain}mm`;

    desc.append(crop, details);

    const time = document.createElement('div');
    time.className = 'time';
    time.textContent = x.time;

    item.append(desc, time);

    // Clicking a history entry restores values into the form!
    item.addEventListener('click', () => {
      document.querySelector('[name="Nitrogen"]').value = x.n;
      document.querySelector('[name="Phosphorus"]').value = x.p;
      document.querySelector('[name="Potassium"]').value = x.k;
      document.querySelector('[name="Temperature"]').value = x.temp;
      document.querySelector('[name="Humidity"]').value = x.hum;
      document.querySelector('[name="Ph"]').value = x.ph;
      document.querySelector('[name="Rainfall"]').value = x.rain;
      updateAllLiveBadges();
      window.scrollTo({ top: document.querySelector('.predict-card').offsetTop - 20, behavior: 'smooth' });
      showToast(`Restored inputs for ${x.crop} 🌱`, 'info');
    });

    list.appendChild(item);
  });
}

function clearHistory() {
  if (confirm('Clear your prediction history from this browser?')) {
    setHistory([]);
    loadHistory();
    updateNavActivityBadges();
    showToast('Prediction history cleared from this device', 'info');
  }
}

function exportHistory() {
  const h = getHistory();
  if (!h.length) {
    showToast('No history entries to export.', 'info');
    return;
  }

  const headers = ['Crop', 'Nitrogen', 'Phosphorus', 'Potassium', 'Temperature_C', 'Humidity_Percent', 'pH', 'Rainfall_mm', 'Recorded_Time'];
  const rows = h.map(item => [
    `"${item.crop}"`,
    item.n,
    item.p,
    item.k,
    item.temp,
    item.hum,
    item.ph,
    item.rain,
    `"${item.time}"`
  ].join(','));

  const csvContent = [headers.join(','), ...rows].join('\r\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `crop_predictions_${currentUser || 'export'}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  showToast('History exported as CSV', 'success');
}

/* ─── REMEMBERED USERS & PROFILE DRAWER SYSTEM ──────────────────────────── */
function getRememberedProfiles() {
  try {
    const raw = localStorage.getItem('crop_saved_profiles');
    const arr = JSON.parse(raw || '[]');
    return Array.isArray(arr) ? arr : [];
  } catch (_) {
    return [];
  }
}

function saveRememberedProfile(username) {
  if (!username) return;
  let profiles = getRememberedProfiles();
  profiles = profiles.filter(p => p.username.toLowerCase() !== username.toLowerCase());
  const history = getHistoryForUser(username);
  profiles.unshift({
    username,
    lastActive: new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
    timestamp: Date.now(),
    predictionCount: history.length
  });
  if (profiles.length > 10) profiles.pop();
  try {
    localStorage.setItem('crop_saved_profiles', JSON.stringify(profiles));
  } catch (_) {}
  updateRememberedUsersUI();
}

function removeRememberedProfile(username) {
  let profiles = getRememberedProfiles();
  profiles = profiles.filter(p => p.username.toLowerCase() !== username.toLowerCase());
  try {
    localStorage.setItem('crop_saved_profiles', JSON.stringify(profiles));
  } catch (_) {}
  updateRememberedUsersUI();
  populateDrawerAccounts();
  showToast(`Removed ${username} from device`, 'info');
}

function getHistoryForUser(username) {
  if (!username) return [];
  try {
    const raw = localStorage.getItem(`crop_history_${username}`);
    const history = JSON.parse(raw || '[]');
    return Array.isArray(history)
      ? history.filter(x => x && typeof x === 'object').slice(0, 50)
      : [];
  } catch (_) {
    return [];
  }
}

function updateNavActivityBadges() {
  const history = getHistory();
  const count = history.length;
  const badge1 = document.getElementById('navActivityCount');
  const badge2 = document.getElementById('navActivityCount2');
  if (badge1) badge1.textContent = count;
  if (badge2) badge2.textContent = count;
}

function updateRememberedUsersUI() {
  const container = document.getElementById('rememberedUsersContainer');
  const list = document.getElementById('rememberedUsersList');
  if (!container || !list) return;

  const profiles = getRememberedProfiles();
  if (!profiles.length) {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'block';
  list.replaceChildren();

  profiles.forEach(p => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'quick-user-chip';
    chip.setAttribute('title', `Sign in as ${p.username} (${p.predictionCount || 0} past predictions)`);
    chip.innerHTML = `<i class="fa-solid fa-user" aria-hidden="true"></i> ${p.username}`;
    chip.onclick = () => {
      document.getElementById('loginUser').value = p.username;
      const passField = document.getElementById('loginPass');
      if (passField) passField.focus();
    };
    list.appendChild(chip);
  });
}

let lastFocusedBeforeDrawer = null;

function openProfileDrawer() {
  if (!currentUser) return;

  const drawer = document.getElementById('profileDrawer');
  const backdrop = document.getElementById('profileDrawerBackdrop');
  if (!drawer || !backdrop) return;

  lastFocusedBeforeDrawer = document.activeElement;

  document.getElementById('drawerUsername').textContent = currentUser;
  document.getElementById('drawerAvatar').textContent = currentUser.charAt(0).toUpperCase();

  const history = getHistory();
  document.getElementById('drawerTotalCount').textContent = history.length;

  if (history.length) {
    const counts = {};
    history.forEach(item => {
      const c = (item.crop || '').toLowerCase();
      counts[c] = (counts[c] || 0) + 1;
    });
    let topCrop = '—', maxCount = 0;
    for (const [c, cnt] of Object.entries(counts)) {
      if (cnt > maxCount) {
        maxCount = cnt;
        topCrop = c.charAt(0).toUpperCase() + c.slice(1);
      }
    }
    document.getElementById('drawerTopCrop').textContent = `${topCrop} (${maxCount})`;
    document.getElementById('drawerLastActive').textContent = history[0].time ? history[0].time.split(',')[0] : 'Today';
  } else {
    document.getElementById('drawerTopCrop').textContent = '—';
    document.getElementById('drawerLastActive').textContent = 'None yet';
  }

  populateDrawerActivity();
  populateDrawerAccounts();

  backdrop.classList.add('show');
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  document.querySelectorAll('.user-pill-btn').forEach(b => b.setAttribute('aria-expanded', 'true'));

  const closeBtn = drawer.querySelector('.btn-close-drawer');
  if (closeBtn) {
    setTimeout(() => closeBtn.focus(), 50);
  }
}

function closeProfileDrawer() {
  const drawer = document.getElementById('profileDrawer');
  const backdrop = document.getElementById('profileDrawerBackdrop');
  if (drawer) {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
  }
  if (backdrop) backdrop.classList.remove('show');
  document.querySelectorAll('.user-pill-btn').forEach(b => b.setAttribute('aria-expanded', 'false'));
  if (lastFocusedBeforeDrawer && typeof lastFocusedBeforeDrawer.focus === 'function') {
    try { lastFocusedBeforeDrawer.focus(); } catch (_) {}
    lastFocusedBeforeDrawer = null;
  }
}

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const drawer = document.getElementById('profileDrawer');
    if (drawer && drawer.classList.contains('open')) {
      closeProfileDrawer();
    }
  }
});

function switchDrawerTab(tab) {
  const btnAct = document.getElementById('tabDrawerActivity');
  const btnAcc = document.getElementById('tabDrawerAccounts');
  const paneAct = document.getElementById('drawerTabActivity');
  const paneAcc = document.getElementById('drawerTabAccounts');

  if (tab === 'activity') {
    if (btnAct) btnAct.classList.add('active');
    if (btnAcc) btnAcc.classList.remove('active');
    if (paneAct) paneAct.classList.add('active');
    if (paneAcc) paneAcc.classList.remove('active');
  } else {
    if (btnAct) btnAct.classList.remove('active');
    if (btnAcc) btnAcc.classList.add('active');
    if (paneAct) paneAct.classList.remove('active');
    if (paneAcc) paneAcc.classList.add('active');
  }
}

function populateDrawerActivity() {
  const feed = document.getElementById('drawerActivityFeed');
  if (!feed) return;

  const history = getHistory();
  if (!history.length) {
    feed.innerHTML = `
      <div class="text-center py-4 text-muted" style="font-size:0.82rem;">
        <i class="fa-solid fa-seedling fa-2x mb-2 d-block text-success" aria-hidden="true"></i>
        No past predictions recorded yet for this user profile.
      </div>
    `;
    return;
  }

  feed.replaceChildren();

  history.forEach(item => {
    const card = document.createElement('div');
    card.className = 'drawer-act-item';

    const top = document.createElement('div');
    top.className = 'drawer-act-top';

    const crop = document.createElement('span');
    crop.className = 'drawer-act-crop';
    crop.textContent = `🌱 ${item.crop}`;

    const time = document.createElement('span');
    time.className = 'drawer-act-time';
    time.textContent = item.time || '';

    top.append(crop, time);

    const details = document.createElement('div');
    details.className = 'drawer-act-details';
    details.textContent = `N:${item.n} P:${item.p} K:${item.k} | ${item.temp}°C | ${item.hum}% | pH ${item.ph} | ${item.rain}mm`;

    const restoreBtn = document.createElement('button');
    restoreBtn.type = 'button';
    restoreBtn.className = 'btn-act-restore';
    restoreBtn.innerHTML = '<i class="fa-solid fa-arrow-rotate-left me-1" aria-hidden="true"></i> Restore to Form';
    restoreBtn.onclick = () => {
      document.querySelector('[name="Nitrogen"]').value = item.n;
      document.querySelector('[name="Phosphorus"]').value = item.p;
      document.querySelector('[name="Potassium"]').value = item.k;
      document.querySelector('[name="Temperature"]').value = item.temp;
      document.querySelector('[name="Humidity"]').value = item.hum;
      document.querySelector('[name="Ph"]').value = item.ph;
      document.querySelector('[name="Rainfall"]').value = item.rain;
      updateAllLiveBadges();
      closeProfileDrawer();
      showView('predict');
      showToast(`Restored ${item.crop} parameters to form 🌱`, 'info');
    };

    card.append(top, details, restoreBtn);
    feed.appendChild(card);
  });
}

function populateDrawerAccounts() {
  const list = document.getElementById('drawerAccountsList');
  const countEl = document.getElementById('drawerAccountsCount');
  if (!list) return;

  const profiles = getRememberedProfiles();
  if (countEl) countEl.textContent = profiles.length;

  if (!profiles.length) {
    list.innerHTML = `<div class="text-muted text-center py-3" style="font-size:0.8rem;">No saved accounts found on this device.</div>`;
    return;
  }

  list.replaceChildren();

  profiles.forEach(p => {
    const card = document.createElement('div');
    card.className = 'drawer-account-item';

    const left = document.createElement('div');
    const name = document.createElement('div');
    name.className = 'account-info-name';
    name.innerHTML = `${p.username} ${p.username.toLowerCase() === (currentUser || '').toLowerCase() ? '<span class="badge bg-success ms-1" style="font-size:0.65rem;">Active</span>' : ''}`;

    const meta = document.createElement('div');
    meta.className = 'account-info-meta';
    meta.textContent = `${p.predictionCount || 0} predictions • Active ${p.lastActive || 'recently'}`;
    left.append(name, meta);

    const right = document.createElement('div');
    right.className = 'd-flex align-items-center gap-2';

    if (p.username.toLowerCase() !== (currentUser || '').toLowerCase()) {
      const switchBtn = document.createElement('button');
      switchBtn.type = 'button';
      switchBtn.className = 'btn-switch-account';
      switchBtn.textContent = 'Switch';
      switchBtn.onclick = () => switchProfileAccount(p.username);
      right.appendChild(switchBtn);
    }

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'btn-del-account';
    delBtn.setAttribute('title', 'Remove account from this device');
    delBtn.innerHTML = '<i class="fa-solid fa-trash-can" aria-hidden="true"></i>';
    delBtn.onclick = () => removeRememberedProfile(p.username);
    right.appendChild(delBtn);

    card.append(left, right);
    list.appendChild(card);
  });
}

async function switchProfileAccount(targetUsername) {
  closeProfileDrawer();
  await handleLogout();
  showView('login');
  const userField = document.getElementById('loginUser');
  if (userField) userField.value = targetUsername;
  const pass = document.getElementById('loginPass');
  if (pass) pass.focus();
  showToast(`Switched account to ${targetUsername}. Enter password to sign in.`, 'info');
}

/* ─── INITIALIZE SESSION WITH RECOVERABLE RETRY ─────────────────────────── */
try {
  ['crop_users_registry', 'crop_logged', 'crop_user'].forEach(key => localStorage.removeItem(key));
} catch (_) {}

async function initializeSession() {
  initTheme();
  updateRememberedUsersUI();
  updateNavActivityBadges();
  const button = document.getElementById('authSubmit');
  const errorEl = document.getElementById('loginError');
  const errorText = document.getElementById('loginErrorText');

  if (button) button.disabled = true;
  const initialView = (window.location && window.location.pathname === '/login') ? 'login' : 'landing';
  showView(initialView);

  const maxRetries = 2;
  const retryDelays = [2000, 4000];

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 12000);

      const response = await fetch('/api/session', {
        cache: 'no-store',
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        if (response.status === 502 || response.status === 503) {
          throw new Error('SERVER_STARTING');
        }
        if (response.status === 429) {
          throw new Error('RATE_LIMITED');
        }
        throw new Error('SESSION_FAILED');
      }

      let data;
      try {
        data = await response.json();
      } catch (_) {
        throw new Error('INVALID_RESPONSE');
      }

      csrfToken = data.csrf_token || '';
      currentUser = data.username || null;

      if (currentUser) {
        proceedToLogin(currentUser);
      }

      if (button) button.disabled = false;
      if (errorEl) {
        errorEl.style.display = 'none';
        delete errorEl.dataset.persistent;
      }
      return;
    } catch (error) {
      const isLast = attempt === maxRetries;
      let userMsg = '';

      if (error.name === 'AbortError' || error.message === 'SERVER_STARTING') {
        userMsg = 'The backend server is waking up (Render free tier may take up to 60 seconds). ';
      } else if (error.message === 'RATE_LIMITED') {
        userMsg = 'Rate limit reached. Please wait before retrying.';
        if (errorText) errorText.textContent = userMsg;
        if (errorEl) {
          errorEl.style.display = 'block';
          errorEl.dataset.persistent = 'true';
        }
        break;
      } else if (error.message === 'INVALID_RESPONSE') {
        userMsg = 'Received an invalid response from server. ';
      } else {
        userMsg = 'Unable to connect to the backend server. ';
      }

      if (!isLast) {
        userMsg += `Retrying connection (${attempt + 2}/${maxRetries + 1})…`;
        if (errorText) errorText.textContent = userMsg;
        if (errorEl) {
          errorEl.style.display = 'block';
          errorEl.dataset.persistent = 'true';
        }
        await new Promise(r => setTimeout(r, retryDelays[attempt]));
      } else {
        userMsg += 'Please click Retry or refresh the page.';
        if (errorText) {
          errorText.replaceChildren();
          errorText.appendChild(document.createTextNode(userMsg + ' '));
          const retryBtn = document.createElement('button');
          retryBtn.type = 'button';
          retryBtn.className = 'btn btn-sm btn-outline-danger ms-2';
          retryBtn.style.padding = '2px 8px';
          retryBtn.style.fontSize = '0.78rem';
          retryBtn.textContent = 'Retry now';
          retryBtn.onclick = () => initializeSession();
          errorText.appendChild(retryBtn);
        }
        if (errorEl) {
          errorEl.style.display = 'block';
          errorEl.dataset.persistent = 'true';
        }
      }
    }
  }
}

// Start session initialization upon script load
initializeSession();
