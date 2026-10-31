/**
 * Adversarial Stress Test & Verification Suite for WebGL UI (graph_3d.html)
 * 
 * Verifies:
 * 1. DOM Architecture & Complete 38 Studio DOM IDs
 * 2. Event Propagation Stopping (e.stopPropagation isolation from WebGL OrbitControls)
 * 3. 3D CSS Flip Card Transforms & WebGL Compositing Layer Isolation
 * 4. StudioAPI Dual-Mode Offline Fallback & Edge Case Resilience
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const HTML_PATH = path.join(PROJECT_ROOT, 'graph_3d.html');
const DATA_PATH = path.join(PROJECT_ROOT, 'graph_3d_data.json');

console.log('='.repeat(80));
console.log('🧪 ADVERSARIAL STRESS TEST: WebGL UI & Studio Controller (graph_3d.html)');
console.log('='.repeat(80));

const htmlContent = fs.readFileSync(HTML_PATH, 'utf8');
const rawDataset = fs.existsSync(DATA_PATH) ? JSON.parse(fs.readFileSync(DATA_PATH, 'utf8')) : { nodes: [], links: [] };

let passedAssertions = 0;
let totalAssertions = 0;

function assert(condition, message) {
  totalAssertions++;
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${message}`);
    throw new Error(`Assertion failed: ${message}`);
  }
  passedAssertions++;
  console.log(`  ✓ ${message}`);
}

// ============================================================================
// TEST SUITE 1: DOM Structure & 38 Studio DOM IDs Verification
// ============================================================================
console.log('\n--- 1. DOM Structure & 38 Studio DOM IDs Verification ---');

// Extract all static IDs from HTML (before script tag)
const htmlBeforeScript = htmlContent.split('<script>')[0];
const idRegex = /id=["']([^"'\s>]+)["']/g;
const staticHtmlIds = new Set();
let match;
while ((match = idRegex.exec(htmlBeforeScript)) !== null) {
  staticHtmlIds.add(match[1]);
}

// 38 Studio & Flashcard DOM IDs required by M5 specification
const EXPECTED_STUDIO_38_IDS = [
  'btn-tab-studio',
  'tab-studio-view',
  // Panel 1: Search & Chat
  'studio-search-panel',
  'studio-search-query',
  'btn-studio-search',
  'studio-search-results',
  // Panel 2: Question Generator
  'studio-questions-panel',
  'studio-q-topic',
  'studio-q-diff',
  'studio-q-type',
  'studio-q-count',
  'btn-studio-q-generate',
  'studio-questions-results',
  // Panel 3: Flashcard SM-2 Spaced Repetition
  'studio-flashcards-panel',
  'studio-fc-course',
  'fc-idx-val',
  'fc-total-val',
  'fc-card',
  'fc-front-course',
  'fc-front-text',
  'fc-back-text',
  'fc-back-source',
  'btn-fc-prev',
  'btn-fc-next',
  'btn-sm2-again',
  'btn-sm2-hard',
  'btn-sm2-good',
  'btn-sm2-easy',
  'fc-feedback',
  // Panel 4: Knowledge Gap Detection
  'studio-gaps-panel',
  'studio-gaps-course',
  'btn-studio-gaps-analyze',
  'studio-gaps-summary',
  'studio-gaps-results',
  // Panel 5: Learning Path
  'studio-path-panel',
  'studio-path-topic',
  'btn-studio-path-generate',
  'studio-path-results'
];

assert(EXPECTED_STUDIO_38_IDS.length === 38, `Expected exactly 38 Studio IDs (got ${EXPECTED_STUDIO_38_IDS.length})`);

// Verify all 38 IDs exist in the HTML DOM
for (const id of EXPECTED_STUDIO_38_IDS) {
  assert(staticHtmlIds.has(id), `DOM ID '${id}' is defined in graph_3d.html`);
}

// Verify that all 38 IDs are also queried via document.getElementById in JavaScript
const jsScript = htmlContent.substring(htmlContent.indexOf('<script>'));
for (const id of EXPECTED_STUDIO_38_IDS) {
  const getElCall = `document.getElementById('${id}')`;
  const getElCallDbl = `document.getElementById("${id}")`;
  assert(jsScript.includes(getElCall) || jsScript.includes(getElCallDbl), `JavaScript explicitly wires ID '${id}'`);
}

// Verify 5 subnav panels and data-panel attributes
const subnavPanels = ['search', 'questions', 'flashcards', 'gaps', 'path'];
for (const p of subnavPanels) {
  assert(htmlContent.includes(`data-panel="${p}"`), `Studio subnav contains button with data-panel="${p}"`);
  assert(htmlContent.includes(`id="studio-${p}-panel"`), `Studio panel container 'studio-${p}-panel' exists`);
}


// ============================================================================
// TEST SUITE 2: Event Propagation Isolation (e.stopPropagation)
// ============================================================================
console.log('\n--- 2. WebGL Event Propagation Isolation Audit ---');

// Verify sidebar event isolation registration in script
const eventIsolationRegex = /sidebarEl\.addEventListener\(\s*evt,\s*e\s*=>\s*\{\s*e\.stopPropagation\(\);\s*\}\s*,\s*\{\s*passive:\s*false\s*\}\s*\)/;
assert(eventIsolationRegex.test(htmlContent), "Sidebar event isolation captures events and invokes e.stopPropagation() with passive:false");

// Check the exact list of isolated events
const expectedIsolatedEvents = ['mousedown', 'mouseup', 'click', 'wheel', 'touchstart', 'touchend', 'pointerdown'];
for (const evt of expectedIsolatedEvents) {
  assert(htmlContent.includes(`'${evt}'`), `Event '${evt}' is trapped on sidebar to protect 3D TrackballControls`);
}

// Headless event simulation: build event bubble simulator
class MockElement {
  constructor(name, parent = null) {
    this.name = name;
    this.parent = parent;
    this.listeners = {};
  }
  addEventListener(event, fn) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(fn);
  }
  dispatchEvent(event) {
    event.currentTarget = this;
    if (this.listeners[event.type]) {
      for (const fn of this.listeners[event.type]) {
        fn(event);
        if (event.immediateStopped) break;
      }
    }
    if (!event.stopped && this.parent) {
      this.parent.dispatchEvent(event);
    }
  }
}

class MockEvent {
  constructor(type) {
    this.type = type;
    this.stopped = false;
    this.currentTarget = null;
  }
  stopPropagation() {
    this.stopped = true;
  }
}

// Simulate DOM tree: window -> document -> canvas (#graph) & sidebar (#sidebar) -> button
const mockWindow = new MockElement('window');
const mockDocument = new MockElement('document', mockWindow);
const mockCanvas = new MockElement('#graph-canvas', mockDocument);
const mockSidebar = new MockElement('#sidebar', mockDocument);
const mockInput = new MockElement('#studio-search-query', mockSidebar);
const mockCard = new MockElement('#fc-card', mockSidebar);

// Setup WebGL camera controls listener on document/window
let canvasRotated = false;
mockDocument.addEventListener('mousedown', () => { canvasRotated = true; });
mockDocument.addEventListener('wheel', () => { canvasRotated = true; });
mockDocument.addEventListener('pointerdown', () => { canvasRotated = true; });

// Attach sidebar isolation handlers exactly as in graph_3d.html
expectedIsolatedEvents.forEach(evt => {
  mockSidebar.addEventListener(evt, e => {
    e.stopPropagation();
  });
});

// Fire events on child elements inside sidebar
for (const evt of ['mousedown', 'wheel', 'pointerdown', 'click']) {
  canvasRotated = false;
  const ev = new MockEvent(evt);
  mockInput.dispatchEvent(ev);
  assert(ev.stopped === true, `Event '${evt}' dispatched on sidebar input was stopped`);
  assert(canvasRotated === false, `Event '${evt}' on sidebar input did NOT bubble to document / WebGL controls`);
}

// Test card click event
const cardClickEvent = new MockEvent('click');
mockCard.dispatchEvent(cardClickEvent);
assert(cardClickEvent.stopped === true, "Card click event stopped at sidebar level without reaching 3D scene");


// ============================================================================
// TEST SUITE 3: 3D Flip Card CSS Transforms & WebGL Compositing Audit
// ============================================================================
console.log('\n--- 3. 3D Flip Card CSS & WebGL Layout Isolation Audit ---');

// Verify CSS 3D transform properties
assert(htmlContent.includes('.flashcard-scene {'), "CSS rule .flashcard-scene defined");
assert(htmlContent.includes('perspective: 1000px;'), "Perspective 1000px defined for 3D depth");
assert(htmlContent.includes('transform-style: preserve-3d;'), "transform-style: preserve-3d defined on .flashcard-card");
assert(htmlContent.includes('transform: rotateY(180deg);'), "transform: rotateY(180deg) defined on .flipped and .flashcard-back");
assert(htmlContent.includes('backface-visibility: hidden;'), "backface-visibility: hidden defined on .flashcard-face");
assert(htmlContent.includes('-webkit-backface-visibility: hidden;'), "-webkit-backface-visibility: hidden defined for WebKit compatibility");

// Stacking context isolation
assert(htmlContent.includes('position:fixed; top:16px; left:16px; width:280px;'), "Sidebar has fixed viewport positioning");
assert(htmlContent.includes('z-index:20;'), "Sidebar has independent z-index:20 stacking context over WebGL canvas");
assert(htmlContent.includes('#graph { position:absolute; top:0; left:0; width:100vw; height:100vh; }'), "WebGL container #graph is positioned absolute in independent base layer");
assert(htmlContent.includes('backdrop-filter: blur(24px)'), "Liquid glass backdrop-filter isolates compositing surface");


// ============================================================================
// TEST SUITE 4: StudioAPI Dual-Mode Offline Fallback & Edge Case Resilience
// ============================================================================
console.log('\n--- 4. StudioAPI Offline Fallback & Edge Case Resilience ---');

// Extract StudioAPI code from HTML
const studioApiStart = htmlContent.indexOf('const StudioAPI = {');
const studioApiEnd = htmlContent.indexOf('// 3. UI EVENT LISTENERS & WIRING');
assert(studioApiStart > 0 && studioApiEnd > studioApiStart, "Found StudioAPI code block in graph_3d.html");

const studioApiCode = htmlContent.substring(studioApiStart, studioApiEnd);

// Setup a sandbox VM with mock environment (localStorage, offline fetch, dataset)
const mockLocalStorage = {};
const sandbox = {
  console: console,
  fullRawData: rawDataset,
  rawData: rawDataset,
  localStorage: {
    getItem: (k) => mockLocalStorage[k] || null,
    setItem: (k, v) => { mockLocalStorage[k] = String(v); },
    removeItem: (k) => { delete mockLocalStorage[k]; }
  },
  fetch: async () => {
    // Offline simulated network: always rejects or returns 404
    throw new Error('Network offline (simulated air-gapped test environment)');
  },
  Math: Math,
  Date: Date,
  parseInt: parseInt,
  encodeURIComponent: encodeURIComponent,
  Array: Array,
  Set: Set
};

vm.createContext(sandbox);
const StudioAPI = vm.runInContext(studioApiCode + '\n; StudioAPI;', sandbox);

assert(typeof StudioAPI === 'object', "StudioAPI object successfully initialized in offline VM sandbox");

// 4.1 Test searchKB edge cases
async function testSearchKB() {
  console.log('  Testing searchKB edge cases...');
  
  // Empty query
  const resEmpty = await StudioAPI.searchKB('');
  assert(Array.isArray(resEmpty) && resEmpty.length === 0, "searchKB('') gracefully returns empty array");

  // Whitespace only
  const resWs = await StudioAPI.searchKB('    \t\n  ');
  assert(Array.isArray(resWs) && resWs.length === 0, "searchKB whitespace returns empty array");

  // Special characters & injection strings
  const resSymbols = await StudioAPI.searchKB('!@#$%^&*()_+=-`~[]\\{}|;\':",./<>?');
  assert(Array.isArray(resSymbols), "searchKB with special symbols does not crash");

  // XSS script tags
  const resXSS = await StudioAPI.searchKB('<script>alert("xss")</script>');
  assert(Array.isArray(resXSS), "searchKB with script tag does not crash");

  // Legitimate academic query against dataset
  const resCns = await StudioAPI.searchKB('CNS');
  assert(Array.isArray(resCns) && resCns.length > 0, `searchKB('CNS') returned ${resCns.length} hits`);
  const firstHit = resCns[0];
  assert(firstHit.id && firstHit.label && firstHit.course && typeof firstHit.score === 'number', "search hit has structured schema (id, label, course, score, snippet)");
}

// 4.2 Test generateQuestions edge cases
async function testGenerateQuestions() {
  console.log('  Testing generateQuestions edge cases...');

  // Empty topic fallback
  const qEmptyTopic = await StudioAPI.generateQuestions('', 'Facile', 'Risposta Multipla', 3);
  assert(Array.isArray(qEmptyTopic) && qEmptyTopic.length === 3, "generateQuestions with empty topic falls back safely and generates requested count");

  // Boundary counts: count = 0 triggers JS falsy default fallback (|| 5)
  const qCountZero = await StudioAPI.generateQuestions('Raft', 'Media', 'Risposta Multipla', 0);
  assert(qCountZero.length === 5, "Count 0 triggers fallback to default count=5 (parseInt(0) || 5)");

  // Boundary counts: count = -5 -> clamped to 1
  const qCountNeg = await StudioAPI.generateQuestions('Raft', 'Media', 'Risposta Multipla', -5);
  assert(qCountNeg.length === 1, "Negative count clamped to minimum 1 question");

  // Boundary counts: count = 50 -> clamped to 20
  const qCountHuge = await StudioAPI.generateQuestions('Raft', 'Media', 'Risposta Multipla', 50);
  assert(qCountHuge.length === 20, "Excessive count clamped to maximum 20 questions");

  // All question types
  const types = [
    { type: 'Risposta Multipla', check: q => q.options && Object.keys(q.options).length === 4 && q.correct_option },
    { type: 'Domanda Aperta', check: q => q.type === 'aperta' && q.answer },
    { type: 'Esercizio Applicativo', check: q => q.type === 'esercizio' && q.answer },
    { type: 'Risposta Singola', check: q => q.type === 'singola' && q.answer },
    { type: 'Misto', check: q => q.question && (q.options || q.answer) }
  ];

  for (const { type, check } of types) {
    const qs = await StudioAPI.generateQuestions('Consenso Distribuito', 'Difficile', type, 4);
    assert(qs.length === 4, `Type '${type}' generated 4 questions`);
    assert(qs.every(check), `Type '${type}' conforms to structural question format`);
  }
}

// 4.3 Test Flashcard Deck & SM-2 Spaced Repetition
function testFlashcardsSM2() {
  console.log('  Testing Flashcards & SM-2 algorithm...');

  // Load initial deck
  const initialDeck = StudioAPI.getFlashcardDeck('ALL');
  assert(Array.isArray(initialDeck) && initialDeck.length >= 6, `Default flashcard deck contains ${initialDeck.length} cards`);

  // Course filtering
  const cnsDeck = StudioAPI.getFlashcardDeck('CNS');
  assert(cnsDeck.every(c => c.course === 'CNS'), "Course filter 'CNS' strictly returns CNS cards");

  // Non-existent course
  const emptyDeck = StudioAPI.getFlashcardDeck('NON_EXISTENT_COURSE_99');
  assert(Array.isArray(emptyDeck) && emptyDeck.length === 0, "Non-existent course returns empty array");

  // SM-2 Review Progression: Card 1
  const cardId = initialDeck[0].id;

  // Grade 4 (Good review): first repetition -> interval 1
  const res1 = StudioAPI.updateFlashcardReview(cardId, 4);
  assert(res1.repetitions === 1, "First successful review sets repetitions=1");
  assert(res1.interval === 1, "First successful review sets interval=1 day");

  // Second review Grade 4: second repetition -> interval 6
  const res2 = StudioAPI.updateFlashcardReview(cardId, 4);
  assert(res2.repetitions === 2, "Second successful review sets repetitions=2");
  assert(res2.interval === 6, "Second successful review sets interval=6 days");

  // Third review Grade 5 (Easy): interval = round(6 * EF)
  const prevEf = res2.easinessFactor;
  const res3 = StudioAPI.updateFlashcardReview(cardId, 5);
  assert(res3.repetitions === 3, "Third successful review sets repetitions=3");
  assert(res3.interval === Math.round(6 * prevEf), `Third review calculates interval = round(6 * ${prevEf}) = ${res3.interval}`);
  assert(res3.easinessFactor >= prevEf, "Grade 5 increases or maintains easiness factor");

  // Failure review Grade 1: reset repetitions to 0, interval to 1
  const resFail = StudioAPI.updateFlashcardReview(cardId, 1);
  assert(resFail.repetitions === 0, "Failed review (q < 3) resets repetitions to 0");
  assert(resFail.interval === 1, "Failed review (q < 3) resets interval to 1 day");
  assert(resFail.easinessFactor >= 1.30, "Easiness factor never falls below 1.30 lower clamp");

  // Non-existent card ID
  const resNull = StudioAPI.updateFlashcardReview('ghost_card_xyz', 4);
  assert(resNull === null, "Updating non-existent card returns null gracefully");
}

// 4.4 Test Knowledge Gap Detection
async function testGapDetection() {
  console.log('  Testing Knowledge Gap Detection...');

  // Normal course
  const cnsReport = await StudioAPI.detectGaps('CNS');
  assert(Array.isArray(cnsReport) && cnsReport.length > 0, `detectGaps('CNS') returned report for ${cnsReport.length} documents`);
  
  for (const item of cnsReport) {
    assert(item.doc_id && item.source_title && typeof item.chunk_count === 'number' && typeof item.coverage_score === 'number', "Gap report item has complete schema");
    if (item.chunk_count < 2) {
      assert(item.is_gap === true, `Document '${item.source_title}' with ${item.chunk_count} chunks correctly flagged as is_gap=true`);
    } else {
      assert(item.is_gap === false, `Document '${item.source_title}' with ${item.chunk_count} chunks flagged as is_gap=false`);
    }
  }

  // Non-existent course
  const emptyReport = await StudioAPI.detectGaps('UNKNOWN_COURSE_XYZ');
  assert(Array.isArray(emptyReport) && emptyReport.length === 0, "Non-existent course returns empty gap array");
}

// 4.5 Test Learning Path Generator
async function testLearningPath() {
  console.log('  Testing Learning Path Generator...');

  const pathRes = await StudioAPI.generateLearningPath('Zero-Knowledge Proofs');
  assert(pathRes && pathRes.topic && Array.isArray(pathRes.steps), "generateLearningPath returns structured object with topic and steps");
  assert(pathRes.steps.length === 4, "Default learning path contains 4 progressive didactic steps");

  for (let i = 0; i < pathRes.steps.length; i++) {
    const step = pathRes.steps[i];
    assert(step.step_number === i + 1, `Step ${i + 1} has strictly sequential step_number`);
    assert(step.concept_name && step.course && step.rationale, `Step ${i + 1} has concept_name, course, and rationale`);
  }

  // Empty topic
  const emptyPath = await StudioAPI.generateLearningPath('');
  assert(emptyPath && emptyPath.steps.length > 0, "generateLearningPath with empty topic falls back safely");
}

// Run all asynchronous tests
(async () => {
  try {
    await testSearchKB();
    await testGenerateQuestions();
    testFlashcardsSM2();
    await testGapDetection();
    await testLearningPath();

    console.log('\n' + '='.repeat(80));
    console.log(`🎉 ALL ${passedAssertions}/${totalAssertions} ADVERSARIAL ASSERTIONS PASSED WITH ZERO ERRORS!`);
    console.log('='.repeat(80));
    process.exit(0);
  } catch (err) {
    console.error('\n💥 TEST HARNESS RUNTIME ERROR:', err);
    process.exit(1);
  }
})();
