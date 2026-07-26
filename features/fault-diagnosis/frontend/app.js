
const API_PATH = '/api/v1/diagnose';
const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function buildApiUrl() {
  var configuredBase = window.DIAGNOSIS_API_BASE_URL || '';
  if (configuredBase) {
    return configuredBase.replace(/\/+$/, '') + API_PATH;
  }

  if (window.location.protocol === 'file:') {
    return DEFAULT_API_BASE_URL + API_PATH;
  }

  if (window.location.port && window.location.port !== '8000') {
    return DEFAULT_API_BASE_URL + API_PATH;
  }

  return API_PATH;
}

const API_URL = buildApiUrl();

// ── State ──────────────────────────────────
let controller = null;
let lastResult = null;
let lastProblemText = '';

// ── DOM References ─────────────────────────
const $container   = document.getElementById('app-container');
const $screens     = {
  input:   document.getElementById('screen-input'),
  loading: document.getElementById('screen-loading'),
  result:  document.getElementById('screen-result'),
  error:   document.getElementById('screen-error'),
};
const $textarea    = document.getElementById('problem-text');
const $btnDiagnose = document.getElementById('btn-diagnose');
const $btnCancel   = document.getElementById('btn-cancel');
const $btnRetry    = document.getElementById('btn-retry');
const $resultBox   = document.getElementById('result-container');
const $errorList   = document.getElementById('error-list');

// Action plan modal
const $apOverlay   = document.getElementById('action-plan-overlay');
const $apBody      = document.getElementById('ap-panel-body');
const $btnApClose  = document.getElementById('btn-ap-close');
const $btnApCopy   = document.getElementById('btn-ap-copy');
const $btnApDismiss = document.getElementById('btn-ap-dismiss');

// ── Screen Management ──────────────────────
function setScreen(name) {
  Object.values($screens).forEach(function (el) { el.classList.remove('active'); });
  var target = $screens[name];
  if (target) {
    target.classList.add('active');
  }
  if (name === 'result') {
    $container.classList.add('app-container--wide');
  } else {
    $container.classList.remove('app-container--wide');
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Helpers ────────────────────────────────
function getDisplayLevel() {
  var el = document.querySelector('input[name="display_level"]:checked');
  return el ? el.value : 'standard';
}

function el(tag, className, text) {
  var node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function clear(parent) {
  while (parent.firstChild) parent.removeChild(parent.firstChild);
}

function safeText(value) {
  if (value === null || value === undefined) return '';
  return String(value);
}

function parseJsonResponse(res) {
  var contentType = res.headers.get('content-type') || '';
  if (contentType.toLowerCase().indexOf('application/json') === -1) {
    return res.text().then(function (body) {
      var target = res.url || API_URL;
      var message = 'Backend did not return JSON from ' + target + '. Make sure FastAPI is running on ' + DEFAULT_API_BASE_URL + '.';

      if (body.indexOf('<!DOCTYPE') !== -1 || body.indexOf('<html') !== -1) {
        message = 'The diagnosis request reached the frontend server instead of FastAPI. Start FastAPI on ' + DEFAULT_API_BASE_URL + ' and retry.';
      }

      throw new Error(message);
    });
  }

  return res.json();
}

function getRequestErrorMessages(err) {
  var message = err.message || '';
  if (message.indexOf('Failed to fetch') !== -1 || message.indexOf('NetworkError') !== -1) {
    return ['Could not reach FastAPI at ' + DEFAULT_API_BASE_URL + '. Start the backend server and retry.'];
  }

  return [message || 'Network error. Please check your connection.'];
}

// ── Submit Diagnosis ───────────────────────
function submitDiagnosis() {
  var text = $textarea.value.trim();
  if (!text) return;

  lastProblemText = text;
  setScreen('loading');

  controller = new AbortController();

  fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      problem_text: text,
      display_level: getDisplayLevel(),
    }),
    signal: controller.signal,
  })
    .then(parseJsonResponse)
    .then(function (data) {
      controller = null;
      if (data.success && data.result) {
        lastResult = data.result;
        renderResult(data.result);
        setScreen('result');
      } else {
        showError(data.errors || ['An unexpected error occurred.']);
      }
    })
    .catch(function (err) {
      controller = null;
      if (err.name === 'AbortError') return;
      showError(getRequestErrorMessages(err));
    });
}

// ── Cancel Request ─────────────────────────
function cancelRequest() {
  if (controller) {
    controller.abort();
    controller = null;
  }
  setScreen('input');
}

// ── Error Handling ─────────────────────────
function showError(errors) {
  clear($errorList);
  errors.forEach(function (msg) {
    var li = el('li', null, safeText(msg));
    $errorList.appendChild(li);
  });
  setScreen('error');
}

// ── Reset ──────────────────────────────────
function resetForm() {
  closeActionPlan();
  lastResult = null;
  lastProblemText = '';
  $textarea.value = '';
  $btnDiagnose.disabled = true;
  clear($resultBox);
  setScreen('input');
}

// ── Result Rendering ───────────────────────
function detectResultType(result) {
  if (result.alternative_paths) return 'expert';
  if (result.diagnostic_checklist) return 'standard';
  if (result.start_here) return 'basic';
  return 'standard';
}

function renderResult(result) {
  clear($resultBox);
  var type = detectResultType(result);

  if (type === 'expert') {
    $container.classList.add('app-container--wide');
  } else {
    $container.classList.remove('app-container--wide');
  }

  var wrap = el('div');

  if (type === 'basic')    renderBasicResult(result, wrap);
  if (type === 'standard') renderStandardResult(result, wrap);
  if (type === 'expert')   renderExpertResult(result, wrap);

  // Original input
  wrap.appendChild(renderOriginalInput());

  // Actions
  wrap.appendChild(renderActions());

  $resultBox.appendChild(wrap);
}

// ── Basic Result ───────────────────────────
function renderBasicResult(result, wrap) {
  // Summary
  wrap.appendChild(renderSection('Summary', function (body) {
    body.appendChild(el('p', 'summary-text', safeText(result.summary)));
  }));

  // Most likely issue
  var issueCard = el('div', 'card card--highlight');
  issueCard.appendChild(el('p', 'section-title', 'Most likely issue'));
  issueCard.appendChild(el('p', 'primary-path-text', safeText(result.most_likely_issue)));
  wrap.appendChild(issueCard);

  // Start here steps
  if (result.start_here && result.start_here.length) {
    wrap.appendChild(renderChecklistPager('Start here', result.start_here, false));
  }
}

// ── Standard Result ────────────────────────
function renderStandardResult(result, wrap) {
  // Summary
  wrap.appendChild(renderSection('Summary', function (body) {
    body.appendChild(el('p', 'summary-text', safeText(result.summary)));
  }));

  // Primary path
  if (result.primary_path) {
    var ppCard = el('div', 'card card--accent');
    ppCard.appendChild(el('p', 'section-title', 'Recommended diagnostic path'));
    ppCard.appendChild(el('p', 'primary-path-text', safeText(result.primary_path)));
    wrap.appendChild(ppCard);
  }

  // Possible causes
  if (result.possible_causes && result.possible_causes.length) {
    wrap.appendChild(renderSection('Possible causes', function (body) {
      body.appendChild(renderList(result.possible_causes, 'cause-list'));
    }));
  }

  // Diagnostic checklist
  if (result.diagnostic_checklist && result.diagnostic_checklist.length) {
    wrap.appendChild(renderChecklistPager('Diagnostic checklist', result.diagnostic_checklist, true));
  }

  // References
  if (result.references_summary && result.references_summary.length) {
    wrap.appendChild(renderReferences(result.references_summary));
  }
}

// ── Expert Result ──────────────────────────
function renderExpertResult(result, wrap) {
  var layout = el('div', 'expert-layout');

  // Summary
  var summaryCard = renderSection('Summary', function (body) {
    body.appendChild(el('p', 'summary-text', safeText(result.summary)));
  });
  summaryCard.classList.add('expert-summary-card');
  layout.appendChild(summaryCard);

  var insightGrid = el('div', 'expert-insight-grid');

  // Primary path
  if (result.primary_path) {
    var ppCard = el('div', 'card card--accent expert-insight-card');
    ppCard.appendChild(el('p', 'section-title', 'Primary path'));
    ppCard.appendChild(el('p', 'primary-path-text', safeText(result.primary_path)));
    insightGrid.appendChild(ppCard);
  }

  // Alternative paths
  if (result.alternative_paths && result.alternative_paths.length) {
    var altCard = renderSection('Alternative paths', function (body) {
      body.appendChild(renderList(result.alternative_paths, 'path-list'));
    });
    altCard.classList.add('expert-insight-card');
    insightGrid.appendChild(altCard);
  }

  // Possible causes
  if (result.possible_causes && result.possible_causes.length) {
    var causeCard = renderSection('Possible causes', function (body) {
      body.appendChild(renderList(result.possible_causes, 'cause-list'));
    });
    causeCard.classList.add('expert-insight-card');
    insightGrid.appendChild(causeCard);
  }

  if (insightGrid.children.length) {
    layout.appendChild(insightGrid);
  }

  // Checklist
  if (result.diagnostic_checklist && result.diagnostic_checklist.length) {
    layout.appendChild(renderChecklistPager('Diagnostic checklist', result.diagnostic_checklist, true));
  }

  // References
  if (result.references_summary && result.references_summary.length) {
    var refsCard = renderReferences(result.references_summary);
    refsCard.classList.add('expert-references-card');
    layout.appendChild(refsCard);
  }

  wrap.appendChild(layout);
}

// ── Shared Components ──────────────────────
function renderSection(title, buildBody) {
  var card = el('div', 'card');
  card.appendChild(el('p', 'section-title', title));
  buildBody(card);
  return card;
}

function getStepNumber(step, index) {
  return step.step_number || step.rank || index + 1;
}

function renderChecklistPager(title, steps, showRef) {
  var state = { index: 0 };
  var total = steps.length;
  var wrap = el('div', 'checklist-pager');
  var heading = el('div', 'checklist-pager__heading');
  heading.appendChild(el('p', 'section-title', title));

  var counter = el('span', 'checklist-pager__counter');
  heading.appendChild(counter);
  wrap.appendChild(heading);

  var stepSlot = el('div', 'checklist-pager__slot');
  wrap.appendChild(stepSlot);

  var nav = el('div', 'checklist-pager__nav');
  var prevBtn = el('button', 'btn btn--secondary checklist-pager__button', 'Previous');
  var nextBtn = el('button', 'btn btn--primary checklist-pager__button', 'Next');
  prevBtn.type = 'button';
  nextBtn.type = 'button';
  nav.appendChild(prevBtn);
  nav.appendChild(nextBtn);
  wrap.appendChild(nav);

  function updateStep() {
    clear(stepSlot);
    var step = steps[state.index];
    var stepNumber = getStepNumber(step, state.index);
    counter.textContent = 'Step ' + (state.index + 1) + ' of ' + total;
    stepSlot.appendChild(renderStepCard(step, stepNumber, showRef));

    prevBtn.disabled = state.index === 0;
    nextBtn.disabled = state.index === total - 1;
  }

  prevBtn.addEventListener('click', function () {
    if (state.index <= 0) return;
    state.index -= 1;
    updateStep();
  });

  nextBtn.addEventListener('click', function () {
    if (state.index >= total - 1) return;
    state.index += 1;
    updateStep();
  });

  updateStep();
  return wrap;
}

function renderStepCard(step, number, showRef) {
  var card = el('div', 'step-card');

  // Header row
  var header = el('div', 'step-card__header');
  header.appendChild(el('span', 'step-card__number', String(number)));
  header.appendChild(el('span', 'step-card__title', safeText(step.title)));
  card.appendChild(header);

  // Fields
  var fields = [
    { label: 'Action', value: step.action },
    { label: 'Expected outcome', value: step.expected },
    { label: 'If this fails', value: step.if_this_fails },
  ];

  fields.forEach(function (f) {
    if (!f.value) return;
    var group = el('div', 'step-card__field');
    group.appendChild(el('p', 'step-card__field-label', f.label));
    group.appendChild(el('p', 'step-card__field-value', safeText(f.value)));
    card.appendChild(group);
  });

  // Reference
  if (showRef && step.reference && step.reference.url) {
    var refWrap = el('div', 'step-card__reference');
    refWrap.appendChild(el('p', 'step-card__reference-label', 'Reference for this checkpoint'));
    var link = document.createElement('a');
    link.href = step.reference.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = safeText(step.reference.title || 'Reference');
    refWrap.appendChild(link);
    card.appendChild(refWrap);
  }

  return card;
}

function renderList(items, className) {
  var ul = el('ul', className);
  items.forEach(function (item) {
    ul.appendChild(el('li', null, safeText(item)));
  });
  return ul;
}

function renderReferences(refs) {
  var card = el('div', 'card');
  card.appendChild(el('p', 'section-title', 'References'));
  var ul = el('ul', 'ref-list');
  refs.forEach(function (ref) {
    var li = document.createElement('li');
    var a = document.createElement('a');
    a.href = safeText(ref.url);
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = safeText(ref.title || ref.url);
    li.appendChild(a);
    if (ref.source_type) {
      var badge = el('span', 'ref-list__type', safeText(ref.source_type).replace(/_/g, ' '));
      li.appendChild(badge);
    }
    ul.appendChild(li);
  });
  card.appendChild(ul);
  return card;
}

function renderOriginalInput() {
  var details = document.createElement('details');
  details.className = 'original-input';
  var summary = document.createElement('summary');
  summary.textContent = 'Original problem description';
  details.appendChild(summary);
  var body = el('p', 'original-input__text', lastProblemText);
  details.appendChild(body);
  return details;
}

function renderActions() {
  var bar = el('div', 'result-actions');

  // Action plan button — only if data exists
  if (lastResult && lastResult.action_plan && lastResult.action_plan.length) {
    var apBtn = el('button', 'btn--action-plan', 'Show recommended action plan');
    apBtn.type = 'button';
    apBtn.id = 'btn-open-action-plan';
    apBtn.addEventListener('click', openActionPlan);
    bar.appendChild(apBtn);
  }

  var copyBtn = el('button', 'btn btn--secondary', 'Copy Result');
  copyBtn.type = 'button';
  copyBtn.addEventListener('click', function () { copyResult(copyBtn); });
  bar.appendChild(copyBtn);

  var newBtn = el('button', 'btn btn--primary', 'New Diagnosis');
  newBtn.type = 'button';
  newBtn.style.width = 'auto';
  newBtn.addEventListener('click', resetForm);
  bar.appendChild(newBtn);

  return bar;
}

// ── Action Plan Modal ──────────────────────
function openActionPlan() {
  if (!lastResult || !lastResult.action_plan) return;
  renderActionPlanItems(lastResult.action_plan);
  $apOverlay.classList.add('ap-overlay--visible');
  $apOverlay.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  // Focus the close button for accessibility
  $btnApClose.focus();
}

function closeActionPlan() {
  $apOverlay.classList.remove('ap-overlay--visible');
  $apOverlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

function renderActionPlanItems(items) {
  clear($apBody);

  if (!items || !items.length) {
    $apBody.appendChild(el('p', 'ap-empty', 'No action plan available.'));
    return;
  }

  items.forEach(function (item, index) {
    var row = el('div', 'ap-item');

    // Checkbox
    var checkWrap = el('label', 'ap-item__check');
    var checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.setAttribute('aria-label', 'Mark step ' + (item.rank || index + 1) + ' complete');
    var checkmark = el('span', 'ap-item__checkmark', '✓');
    checkWrap.appendChild(checkbox);
    checkWrap.appendChild(checkmark);
    row.appendChild(checkWrap);

    // Toggle checked styling
    checkbox.addEventListener('change', function () {
      if (checkbox.checked) {
        row.classList.add('ap-item--checked');
      } else {
        row.classList.remove('ap-item--checked');
      }
    });

    // Content
    var content = el('div', 'ap-item__content');

    // Title with rank badge
    var titleRow = el('p', 'ap-item__title');
    var rankBadge = el('span', 'ap-item__rank', String(item.rank || index + 1));
    titleRow.appendChild(rankBadge);
    titleRow.appendChild(document.createTextNode(safeText(item.title)));
    content.appendChild(titleRow);

    // Fields
    var fields = [
      { label: 'Action', value: item.action },
      { label: 'Expected outcome', value: item.expected },
      { label: 'If this fails', value: item.if_this_fails },
    ];

    fields.forEach(function (f) {
      if (!f.value) return;
      var fieldDiv = el('div', 'ap-item__field');
      fieldDiv.appendChild(el('p', 'ap-item__field-label', f.label));
      fieldDiv.appendChild(el('p', 'ap-item__field-value', safeText(f.value)));
      content.appendChild(fieldDiv);
    });

    row.appendChild(content);
    $apBody.appendChild(row);
  });
}

function copyActionPlan(btn) {
  if (!lastResult || !lastResult.action_plan) return;
  var text = formatActionPlanText(lastResult.action_plan);
  navigator.clipboard.writeText(text).then(function () {
    var original = btn.textContent;
    btn.textContent = 'Copied!';
    btn.classList.add('btn--copied');
    setTimeout(function () {
      btn.textContent = original;
      btn.classList.remove('btn--copied');
    }, 1500);
  }).catch(function () {
    // silent fallback
  });
}

function formatActionPlanText(items) {
  var lines = ['Recommended Action Plan', ''];
  items.forEach(function (item, i) {
    var num = item.rank || i + 1;
    lines.push('Step ' + num + ': ' + (item.title || ''));
    if (item.action) lines.push('  Action: ' + item.action);
    if (item.expected) lines.push('  Expected: ' + item.expected);
    if (item.if_this_fails) lines.push('  If this fails: ' + item.if_this_fails);
    lines.push('');
  });
  return lines.join('\n');
}

// ── Copy Result ────────────────────────────
function copyResult(btn) {
  if (!lastResult) return;
  var text = formatResultText(lastResult);
  navigator.clipboard.writeText(text).then(function () {
    var original = btn.textContent;
    btn.textContent = 'Copied!';
    btn.classList.add('btn--copied');
    setTimeout(function () {
      btn.textContent = original;
      btn.classList.remove('btn--copied');
    }, 1500);
  }).catch(function () {
    // silent fallback
  });
}

function formatResultText(r) {
  var lines = [];
  if (r.summary) lines.push('Summary: ' + r.summary);
  if (r.most_likely_issue) lines.push('Most likely issue: ' + r.most_likely_issue);
  if (r.primary_path) lines.push('Primary path: ' + r.primary_path);
  if (r.alternative_paths && r.alternative_paths.length) {
    lines.push('');
    lines.push('Alternative paths:');
    r.alternative_paths.forEach(function (p, i) { lines.push('  ' + (i + 1) + '. ' + p); });
  }
  if (r.possible_causes && r.possible_causes.length) {
    lines.push('');
    lines.push('Possible causes:');
    r.possible_causes.forEach(function (c, i) { lines.push('  ' + (i + 1) + '. ' + c); });
  }
  var steps = r.diagnostic_checklist || r.start_here;
  if (steps && steps.length) {
    lines.push('');
    lines.push('Diagnostic steps:');
    steps.forEach(function (s, i) {
      var num = s.step_number || s.rank || i + 1;
      lines.push('  Step ' + num + ': ' + (s.title || ''));
      if (s.action) lines.push('    Action: ' + s.action);
      if (s.expected) lines.push('    Expected: ' + s.expected);
      if (s.if_this_fails) lines.push('    If this fails: ' + s.if_this_fails);
    });
  }
  if (r.references_summary && r.references_summary.length) {
    lines.push('');
    lines.push('References:');
    r.references_summary.forEach(function (ref) {
      lines.push('  - ' + (ref.title || '') + ': ' + (ref.url || ''));
    });
  }
  return lines.join('\n');
}

// ── Initialisation ─────────────────────────
function init() {
  // Enable/disable diagnose button
  $textarea.addEventListener('input', function () {
    $btnDiagnose.disabled = !$textarea.value.trim();
  });

  // Submit
  $btnDiagnose.addEventListener('click', submitDiagnosis);

  // Cancel
  $btnCancel.addEventListener('click', cancelRequest);

  // Retry / back
  $btnRetry.addEventListener('click', function () { setScreen('input'); });

  // Action plan modal controls
  $btnApClose.addEventListener('click', closeActionPlan);
  $btnApDismiss.addEventListener('click', closeActionPlan);
  $btnApCopy.addEventListener('click', function () { copyActionPlan($btnApCopy); });

  // Close modal on overlay click
  $apOverlay.addEventListener('click', function (e) {
    if (e.target === $apOverlay) closeActionPlan();
  });

  // Close modal on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && $apOverlay.classList.contains('ap-overlay--visible')) {
      closeActionPlan();
    }
  });

  // Keyboard shortcut: Ctrl+Enter to submit
  $textarea.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !$btnDiagnose.disabled) {
      submitDiagnosis();
    }
  });
}

document.addEventListener('DOMContentLoaded', init);
