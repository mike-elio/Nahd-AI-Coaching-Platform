const STORAGE_KEY = "gpes.expert.frontend";
const ANALYSIS_CIRCUMFERENCE = 439.82;
const RESULT_CIRCUMFERENCE = 364.42;

const DOMAIN_META = {
  SE: {
    icon: "terminal",
    badge: "Software Engineering",
    featured: false,
    layoutClass: "md:col-span-4",
    description:
      "Focus on architecting scalable systems, robust backends, and elegant user interfaces.",
    footnote: "Systems & Product",
    filled: false,
    summary:
      "Software engineering emphasizes structured problem solving, implementation depth, and product delivery.",
  },
  AIE: {
    icon: "psychology",
    badge: "Expert Selection",
    featured: true,
    layoutClass: "md:col-span-5",
    description:
      "Dive into machine learning workflows, neural systems, data reasoning, and practical AI product work.",
    footnote: "Trending High Demand",
    filled: true,
    summary:
      "Your answers point toward analytical reasoning, experimentation, and comfort with intelligent systems.",
  },
  CNE: {
    icon: "hub",
    badge: "Network Architecture",
    featured: false,
    layoutClass: "md:col-span-3",
    description:
      "Master digital infrastructure, secure connectivity, cloud networking, and the backbone of resilient systems.",
    footnote: "Infrastructure Ready",
    filled: false,
    summary:
      "You appear to value reliability, systems coordination, and infrastructure-oriented decision making.",
  },
};

const QUESTION_TYPE_LABELS = {
  boolean: "Preference Signal",
  choice: "Technical Assessment",
  multi_choice: "Multi-Select Assessment",
  numeric: "Quantitative Input",
  scale: "Confidence Calibration",
  text: "Open Response",
};

const FALLBACK_REASON =
  "Your answer pattern suggests a strong overall fit for this path based on the balance of interests, strengths, and readiness indicators gathered during the interview.";

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function parseJson(value) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

document.addEventListener("alpine:init", () => {
  Alpine.data("expertApp", () => ({
    booting: true,
    busy: false,
    screen: "home",
    domains: [],
    selectedDomain: "AIE",
    sessionId: null,
    question: null,
    questionOptions: [],
    answer: null,
    errorMessage: "",
    result: null,
    progress: {
      answered_count: 0,
      question_number: 1,
      estimated_total: 1,
      percent: 0,
      can_go_back: false,
    },
    analysisStep: 0,
    analysisTimer: null,
    toast: {
      visible: false,
      title: "",
      message: "",
      icon: "info",
      type: "info",
    },
    toastTimer: null,

    async init() {
      await this.loadDomains();
      await this.restoreSession();
      this.booting = false;
    },

    async api(path, options = {}) {
      const config = {
        method: options.method || "GET",
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(options.headers || {}),
        },
        ...(options.body ? { body: options.body } : {}),
      };

      let response;
      try {
        response = await window.fetch(path, config);
      } catch {
        throw new Error("Unable to reach the expert system backend.");
      }

      const contentType = response.headers.get("content-type") || "";
      const payload = contentType.includes("application/json")
        ? await response.json()
        : { detail: await response.text() };

      if (!response.ok) {
        throw new Error(payload.detail || "Something went wrong while contacting the server.");
      }

      return payload;
    },

    async loadDomains() {
      const stored = this.readStore();
      if (stored?.domain) {
        this.selectedDomain = stored.domain;
      }

      try {
        this.domains = await this.api("/api/expert/domains");
      } catch (error) {
        this.domains = Object.entries(DOMAIN_META).map(([code, meta]) => ({
          code,
          label: meta.badge,
          description: meta.description,
        }));
        this.showToast(error.message, "warning");
      }

      if (!this.domains.some((domain) => domain.code === this.selectedDomain) && this.domains.length) {
        this.selectedDomain = this.domains.find((domain) => domain.code === "AIE")?.code || this.domains[0].code;
      }
    },

    async restoreSession() {
      const stored = this.readStore();
      if (!stored?.sessionId) {
        return;
      }

      this.sessionId = stored.sessionId;
      if (stored.domain) {
        this.selectedDomain = stored.domain;
      }

      try {
        const state = await this.api(`/api/expert/sessions/${this.sessionId}/state`);
        this.selectedDomain = state.domain || this.selectedDomain;
        this.progress = state.progress || this.progress;
        this.persist();

        if (state.is_finished) {
          await this.loadResult({ withAnalysis: false });
          return;
        }

        await this.fetchCurrentQuestion();
      } catch {
        this.resetSessionState();
      }
    },

    readStore() {
      return parseJson(window.localStorage.getItem(STORAGE_KEY)) || {};
    },

    persist() {
      if (!this.sessionId) {
        window.localStorage.removeItem(STORAGE_KEY);
        return;
      }

      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          sessionId: this.sessionId,
          domain: this.selectedDomain,
        }),
      );
    },

    resetSessionState() {
      this.stopAnalysisTicker();
      this.sessionId = null;
      this.question = null;
      this.questionOptions = [];
      this.answer = null;
      this.result = null;
      this.errorMessage = "";
      this.progress = {
        answered_count: 0,
        question_number: 1,
        estimated_total: 1,
        percent: 0,
        can_go_back: false,
      };
      this.screen = "home";
      this.persist();
    },

    chooseDomain(code) {
      this.selectedDomain = code;
      this.persist();
    },

    domainMeta(code) {
      return DOMAIN_META[code] || DOMAIN_META.SE;
    },

    domainCardClasses(code) {
      const meta = this.domainMeta(code);
      const selected = this.selectedDomain === code;
      const base = `${meta.layoutClass} `;

      if (selected) {
        return `${base}bg-surface-container-high border-primary/30 shadow-[0_0_50px_rgba(99,102,241,0.1)]`;
      }

      return `${base}glass-card border-outline/10 hover:border-primary/30`;
    },

    navItems() {
      if (this.screen === "question") {
        return [{ label: "Interview Mode", active: true }];
      }

      if (this.screen === "analysis") {
        return [
          { label: "Analysis", active: true },
          { label: "Results", active: false },
          { label: "Plan", active: false },
        ];
      }

      if (this.screen === "result") {
        return [
          { label: "Results", active: true },
          { label: "Explore", active: false },
          { label: "History", active: false },
        ];
      }

      return [
        { label: "Explore", active: true },
        { label: "Analysis", active: false },
        { label: "Archive", active: false },
      ];
    },

    selectedDomainLabel() {
      const domain = this.domains.find((item) => item.code === this.selectedDomain);
      return domain ? `${domain.code} · ${domain.label}` : this.selectedDomain;
    },

    async startInterview() {
      if (!this.selectedDomain || this.busy) {
        return;
      }

      this.busy = true;
      this.errorMessage = "";

      try {
        const session = await this.api("/api/expert/sessions", {
          method: "POST",
          body: JSON.stringify({ domain: this.selectedDomain }),
        });

        this.sessionId = session.session_id;
        this.result = null;
        this.persist();
        await this.fetchCurrentQuestion();
      } catch (error) {
        this.showToast(error.message, "error");
      } finally {
        this.busy = false;
      }
    },

    async fetchCurrentQuestion() {
      if (!this.sessionId) {
        return;
      }

      const payload = await this.api(`/api/expert/sessions/${this.sessionId}/question`);
      if (payload.finished) {
        await this.loadResult({ withAnalysis: true });
        return;
      }

      this.applyQuestionPayload(payload);
    },

    applyQuestionPayload(payload) {
      this.stopAnalysisTicker();
      this.question = payload.question;
      this.questionOptions = this.buildQuestionOptions(payload.question);
      this.answer = this.normalizeAnswer(payload.question, payload.previous_answer);
      this.progress = payload.progress || this.progress;
      this.errorMessage = "";
      this.result = null;
      this.screen = "question";
    },

    buildQuestionOptions(question) {
      if (!question) {
        return [];
      }

      if (question.type === "boolean") {
        return [
          { value: true, title: "Yes", subtitle: "" },
          { value: false, title: "No", subtitle: "" },
        ];
      }

      if (question.type === "choice" || question.type === "multi_choice") {
        const english = question.choices_en || [];
        return english.map((value) => ({
          value,
          title: value,
          subtitle: "",
        }));
      }

      return [];
    },

    normalizeAnswer(question, previousAnswer) {
      if (!question) {
        return null;
      }

      if (question.type === "multi_choice") {
        return Array.isArray(previousAnswer) ? [...previousAnswer] : [];
      }

      if (question.type === "boolean") {
        if (previousAnswer === true || previousAnswer === "true" || previousAnswer === "Yes") {
          return true;
        }
        if (previousAnswer === false || previousAnswer === "false" || previousAnswer === "No") {
          return false;
        }
        return null;
      }

      if (question.type === "numeric") {
        return previousAnswer ?? "";
      }

      if (question.type === "scale") {
        return previousAnswer ?? null;
      }

      return previousAnswer ?? "";
    },

    questionPrimaryText() {
      return this.question?.text_en || "Question unavailable";
    },

    questionSecondaryText() {
      return "";
    },

    questionTypeLabel(type) {
      return QUESTION_TYPE_LABELS[type] || "Interview Prompt";
    },

    questionHint() {
      if (!this.question) {
        return "";
      }

      if (this.question.type === "multi_choice") {
        return "Select all options that apply.";
      }
      if (this.question.type === "scale") {
        return `Choose a value from ${this.question.scale_min} to ${this.question.scale_max}.`;
      }
      if (this.question.type === "numeric") {
        if (this.hasNumericBounds()) {
          return `Enter a value from ${this.question.numeric_min} to ${this.question.numeric_max}.`;
        }
        return "Enter a valid number to continue.";
      }
      return "Select one option to continue.";
    },

    hasNumericBounds() {
      return (
        this.question?.type === "numeric" &&
        this.question.numeric_min !== null &&
        this.question.numeric_min !== undefined &&
        this.question.numeric_max !== null &&
        this.question.numeric_max !== undefined
      );
    },

    selectOption(value) {
      if (!this.question) {
        return;
      }

      this.errorMessage = "";

      if (this.question.type === "multi_choice") {
        const current = Array.isArray(this.answer) ? [...this.answer] : [];
        this.answer = current.includes(value)
          ? current.filter((item) => item !== value)
          : [...current, value];
        return;
      }

      this.answer = value;
    },

    isSelected(value) {
      if (this.question?.type === "multi_choice") {
        return Array.isArray(this.answer) && this.answer.includes(value);
      }

      return this.answer === value;
    },

    optionButtonClasses(value) {
      if (this.isSelected(value)) {
        return "border border-primary/40 bg-surface-container-high ring-1 ring-primary";
      }

      return "border border-transparent bg-surface-container-low hover:border-outline-variant/20 hover:bg-[#242424]";
    },

    scaleValues() {
      if (!this.question || this.question.type !== "scale") {
        return [];
      }

      const values = [];
      for (let current = Number(this.question.scale_min); current <= Number(this.question.scale_max); current += 1) {
        values.push(current);
      }
      return values;
    },

    scaleButtonClasses(value) {
      return this.answer === value
        ? "border-primary bg-primary/10 text-primary shadow-[0_0_20px_rgba(99,102,241,0.12)]"
        : "border-outline/15 bg-surface-container-low text-on-surface-variant hover:border-primary/30 hover:text-on-surface";
    },

    validateAnswer() {
      if (!this.question) {
        return "No active question found.";
      }

      if (this.question.type === "boolean" && typeof this.answer !== "boolean") {
        return "Choose Yes or No before continuing.";
      }

      if (this.question.type === "choice" && !this.answer) {
        return "Choose one option before continuing.";
      }

      if (this.question.type === "multi_choice" && (!Array.isArray(this.answer) || !this.answer.length)) {
        return "Choose at least one option before continuing.";
      }

      if (this.question.type === "numeric" && (this.answer === "" || this.answer === null || this.answer === undefined)) {
        return "Enter a numeric value before continuing.";
      }

      if (this.question.type === "numeric" && Number.isNaN(Number(this.answer))) {
        return "Enter a valid numeric value before continuing.";
      }

      if (this.question.type === "numeric") {
        const numeric = Number(this.answer);
        if (this.question.numeric_min !== null && this.question.numeric_min !== undefined && numeric < Number(this.question.numeric_min)) {
          return `Value must be at least ${this.question.numeric_min}.`;
        }
        if (this.question.numeric_max !== null && this.question.numeric_max !== undefined && numeric > Number(this.question.numeric_max)) {
          return `Value must be at most ${this.question.numeric_max}.`;
        }
      }

      if (this.question.type === "scale" && this.answer === null) {
        return "Pick a value on the scale before continuing.";
      }

      if (!["boolean", "choice", "multi_choice", "numeric", "scale"].includes(this.question.type) && !this.answer) {
        return "Please provide an answer before continuing.";
      }

      return null;
    },

    serializeAnswer() {
      if (!this.question) {
        return null;
      }

      if (this.question.type === "numeric") {
        return this.answer === "" ? null : Number(this.answer);
      }

      if (this.question.type === "scale") {
        return Number(this.answer);
      }

      return this.answer;
    },

    async nextQuestion() {
      if (!this.sessionId || this.busy) {
        return;
      }

      const validationError = this.validateAnswer();
      if (validationError) {
        this.errorMessage = validationError;
        return;
      }

      this.busy = true;
      this.errorMessage = "";

      try {
        const response = await this.api(`/api/expert/sessions/${this.sessionId}/answer`, {
          method: "POST",
          body: JSON.stringify({ answer: this.serializeAnswer() }),
        });

        this.progress = response.progress || this.progress;

        if (response.is_finished) {
          await this.loadResult({ withAnalysis: true });
          return;
        }

        await this.fetchCurrentQuestion();
      } catch (error) {
        this.errorMessage = error.message;
      } finally {
        this.busy = false;
      }
    },

    async goBack() {
      if (!this.sessionId || this.busy || !this.progress.can_go_back) {
        return;
      }

      this.busy = true;
      this.errorMessage = "";

      try {
        const payload = await this.api(`/api/expert/sessions/${this.sessionId}/back`, {
          method: "POST",
        });
        this.applyQuestionPayload(payload);
      } catch (error) {
        this.showToast(error.message, "warning");
      } finally {
        this.busy = false;
      }
    },

    startAnalysisTicker() {
      this.stopAnalysisTicker();
      this.analysisStep = 0;
      this.analysisTimer = window.setInterval(() => {
        this.analysisStep = (this.analysisStep + 1) % 3;
      }, 520);
    },

    stopAnalysisTicker() {
      if (this.analysisTimer) {
        window.clearInterval(this.analysisTimer);
        this.analysisTimer = null;
      }
    },

    analysisDashOffset() {
      const percent = [0.42, 0.58, 0.74][this.analysisStep] || 0.42;
      return ANALYSIS_CIRCUMFERENCE * (1 - percent);
    },

    analysisNodes() {
      const widths = [
        ["76%", "82%", "88%"],
        ["48%", "56%", "64%"],
        ["28%", "36%", "44%"],
      ];
      const statuses = [
        ["SYNTHESIZING...", "CALIBRATING...", "FINALIZING..."],
        ["MAPPING TRENDS...", "SCORING OPTIONS...", "LOCKING MATCHES..."],
        ["ESTIMATING FIT...", "VERIFYING SIGNALS...", "PREPARING OUTPUT..."],
      ];

      return [
        {
          title: "Cognitive Logic",
          icon: "psychology",
          iconColor: "text-secondary",
          barColor: "bg-secondary",
          width: widths[0][this.analysisStep],
          status: statuses[0][this.analysisStep],
        },
        {
          title: "Market Alignment",
          icon: "database",
          iconColor: "text-primary",
          barColor: "bg-primary",
          width: widths[1][this.analysisStep],
          status: statuses[1][this.analysisStep],
        },
        {
          title: "Skill Validation",
          icon: "verified_user",
          iconColor: "text-tertiary",
          barColor: "bg-tertiary",
          width: widths[2][this.analysisStep],
          status: statuses[2][this.analysisStep],
        },
      ];
    },

    async loadResult({ withAnalysis } = { withAnalysis: true }) {
      if (!this.sessionId) {
        return;
      }

      if (withAnalysis) {
        this.screen = "analysis";
        this.startAnalysisTicker();
      }

      try {
        const resultPromise = this.api(`/api/expert/sessions/${this.sessionId}/result`);
        const result = withAnalysis ? (await Promise.all([resultPromise, wait(1600)]))[0] : await resultPromise;
        this.stopAnalysisTicker();
        this.result = result;
        this.progress.percent = 100;
        this.screen = "result";
        this.persist();
      } catch (error) {
        this.stopAnalysisTicker();
        this.showToast(error.message, "error");
        this.screen = this.question ? "question" : "home";
      }
    },

    displayFitScore() {
      const score = this.numericFitScore();
      return Number.isFinite(score) ? `${Math.round(score)}%` : "N/A";
    },

    numericFitScore() {
      const score =
        this.result?.fit_score ??
        this.result?.selected_goal?.fit_score_percent ??
        this.result?.alternative_goal?.fit_score_percent;
      const numeric = Number(score);
      return Number.isFinite(numeric) ? numeric : null;
    },

    resultDashOffset() {
      const score = this.numericFitScore();
      if (!Number.isFinite(score)) {
        return RESULT_CIRCUMFERENCE;
      }

      const clamped = Math.max(0, Math.min(100, score));
      return RESULT_CIRCUMFERENCE * (1 - clamped / 100);
    },

    selectedGoalHeading() {
      const goal = this.result?.selected_goal?.goal_name;
      return goal ? `${goal} (${this.result.domain})` : `Recommended Track (${this.result?.domain || this.selectedDomain})`;
    },


    primaryReason() {
      const reasons = this.result?.why_selected || [];
      return reasons[0] || FALLBACK_REASON;
    },

    strengthItems() {
      const items = this.result?.strengths || [];
      if (items.length) {
        return items.slice(0, 3);
      }

      return [
        "Consistent decision signals across the interview",
        "Balanced readiness for this track's core work",
      ];
    },

    gapResolutionPlanItems() {
      return (this.result?.gap_resolution_plan || []).slice(0, 4);
    },

    hasGapResolutionPlan() {
      return this.gapResolutionPlanItems().length > 0;
    },

    navigateHome() {
      if (this.screen === "home") {
        return;
      }

      this.resetSessionState();
    },

    restartInterview() {
      this.resetSessionState();
    },

    savePdf() {
      window.print();
    },

    clampedPercent(value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return 0;
      }

      return Math.max(0, Math.min(100, numeric));
    },

    formatPercent(value) {
      return `${Math.round(this.clampedPercent(value))}%`;
    },

    copyrightText() {
      return `© ${new Date().getFullYear()} GPES Expert System`;
    },

    showToast(message, type = "info") {
      if (this.toastTimer) {
        window.clearTimeout(this.toastTimer);
      }

      const config = {
        info: { title: "Heads up", icon: "info" },
        warning: { title: "Check this", icon: "warning" },
        error: { title: "Something failed", icon: "error" },
      }[type] || { title: "Heads up", icon: "info" };

      this.toast = {
        visible: true,
        title: config.title,
        message,
        icon: config.icon,
        type,
      };

      this.toastTimer = window.setTimeout(() => {
        this.toast.visible = false;
      }, 3600);
    },

    toastClasses() {
      if (this.toast.type === "error") {
        return "border-error/30 bg-[#241516]";
      }

      if (this.toast.type === "warning") {
        return "border-tertiary/30 bg-[#241d15]";
      }

      return "border-primary/30 bg-[#171823]";
    },
  }));
});
