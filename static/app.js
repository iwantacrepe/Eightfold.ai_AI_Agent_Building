const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const planContainer = document.getElementById("plan-container");
const sourcesList = document.getElementById("sources-list");
const refreshPlanButton = document.getElementById("refresh-plan");
const downloadPdfButton = document.getElementById("download-pdf");
const hero = document.getElementById("hero");
const planTabButton = document.getElementById("plan-tab");
const chatAreaElement = document.querySelector(".chat-area");
const progressOverlay = document.getElementById("progress-overlay");
const overlayProgressList = document.getElementById("overlay-progress-list");
const progressOverlayTitle = document.getElementById("progress-overlay-title");
const tabButtons = document.querySelectorAll(".tab-button");
const tabPanels = document.querySelectorAll(".tab-panel");
const researchPanel = document.getElementById("research-panel");
const researchActivityList = document.getElementById("research-activity-list");
const statusBanner = document.getElementById("status-banner");
const statusBannerText = document.getElementById("status-banner-text");
const agentConsole = document.getElementById("agent-console");
const agentConsoleList = document.getElementById("agent-console-list");
const workspaceShell = document.querySelector(".workspace");

let firstMessageSent = false;
let currentStage = "planning";
let hasPlan = false;
let activeTab = "chat";
let tabLock = false;
let latestResearchActivity = [];
let latestProgressLog = [];

const CONSOLE_ACTIVE_STAGES = new Set(["researching", "analyzing", "reviewing", "editing", "done"]);

const STRATEGY_AGENT_BLUEPRINTS = [
    { key: "overview", label: "Overview Architect", match: "building overview", detail: "Framing the executive recap" },
    { key: "industry", label: "Industry Analyst", match: "mapping industry", detail: "Scanning macro trends" },
    { key: "financials", label: "Financial Strategist", match: "summarizing financials", detail: "Highlighting growth signals" },
    { key: "talent", label: "Talent Partner", match: "assessing talent", detail: "Identifying hiring focus" },
    { key: "leadership", label: "Leadership Briefing", match: "profiling leadership", detail: "Capturing exec priorities" },
    { key: "news", label: "Trigger Monitor", match: "compiling news", detail: "Flagging fresh catalysts" },
    { key: "swot", label: "SWOT Crafter", match: "drafting swot", detail: "Balancing strengths & risks" },
    { key: "opportunities", label: "Opportunity Mapper", match: "identifying opportunities", detail: "Surfacing best plays" },
    { key: "strategy", label: "GTM Designer", match: "designing strategy", detail: "Shaping GTM motions" },
    { key: "plan_30_60_90", label: "30-60-90 Builder", match: "framing 30-60-90", detail: "Sequencing early moves" },
];

const renderMarkdown = (text = "") => {
    if (window.marked) {
        const raw = window.marked.parse(text);
        if (window.DOMPurify) {
            return window.DOMPurify.sanitize(raw);
        }
        return raw;
    }
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
};

const hideHero = () => {
    if (!hero) return;
    hero.classList.add("hidden");
};

const setOverlayVisible = () => {
    if (!progressOverlay || !chatAreaElement) return;
    progressOverlay.classList.add("hidden");
    chatAreaElement.classList.remove("blurred");
};

const setActiveTab = (tab, manual = false) => {
    if (manual) {
        tabLock = true;
    }
    activeTab = tab;
    tabButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.tab === tab);
    });
    tabPanels.forEach((panel) => {
        panel.classList.toggle("hidden", panel.id !== `${tab}-panel`);
    });
};

const updateStageUI = (stage, planReady = hasPlan) => {
    currentStage = stage;
    hasPlan = planReady;
    if (planTabButton) {
        const enablePlanTab = Boolean(planReady);
        planTabButton.disabled = !enablePlanTab;
        planTabButton.classList.toggle("disabled", !enablePlanTab);
        if (!enablePlanTab && activeTab === "plan") {
            setActiveTab("chat");
        }
    }

    const overlayNeeded = stage === "analyzing";
    setOverlayVisible(overlayNeeded, stage);
    if (overlayNeeded && !tabLock) {
        setActiveTab("research");
    } else if (!overlayNeeded && planReady && stage === "reviewing" && !tabLock) {
        setActiveTab("plan");
    } else if (!overlayNeeded && !tabLock && activeTab !== "chat" && stage !== "reviewing") {
        setActiveTab("chat");
    }

    updateStatusBanner(currentStage);
    renderAgentConsole();
};

const appendMessage = (role, content) => {
    const wrapper = document.createElement("div");
    wrapper.className = `chat-message ${role}`;
    const strong = document.createElement("strong");
    strong.textContent = role === "user" ? "You:" : "Assistant:";
    const paragraph = document.createElement("p");
    paragraph.innerHTML = renderMarkdown(content);
    wrapper.appendChild(strong);
    wrapper.appendChild(paragraph);
    chatWindow.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;
};

const renderProgress = (target, items) => {
    if (!target) return;
    target.innerHTML = "";
    items.forEach((line) => {
        const li = document.createElement("li");
        li.textContent = line;
        target.appendChild(li);
    });
};

const updateProgress = (items) => {
    renderProgress(overlayProgressList, items);
};

const createBadge = (label, variant = "") => {
    const badge = document.createElement("span");
    badge.className = `badge ${variant ? `badge--${variant}` : ""}`.trim();
    badge.textContent = label;
    return badge;
};

const renderResearchActivity = (activity = []) => {
    if (!researchActivityList) return;
    if (!activity.length) {
        researchActivityList.innerHTML =
            '<li class="research-activity-list__empty">No searches yet. Approve the workplan to watch the agents in action.</li>';
        return;
    }

    const fragment = document.createDocumentFragment();
    activity.slice(-18).forEach((event) => {
        const card = document.createElement("li");
        card.className = "activity-card";

        const header = document.createElement("div");
        header.className = "activity-card__header";
        const agentLabel = document.createElement("div");
        agentLabel.className = "activity-card__agent";
        agentLabel.textContent = event.agent || "Agent";
        const status = document.createElement("span");
        const statusValue = (event.status || "running").toLowerCase();
        status.className = `activity-card__status badge badge--status-${statusValue}`;
        status.textContent = statusValue.toUpperCase();
        header.appendChild(agentLabel);
        header.appendChild(status);

        const metaRow = document.createElement("div");
        metaRow.className = "activity-card__meta";
        if (event.source) {
            metaRow.appendChild(createBadge(event.source));
        }
        if (event.channel) {
            metaRow.appendChild(createBadge(event.channel, "channel"));
        }
        if (event.goal) {
            const goal = document.createElement("span");
            goal.className = "activity-card__goal";
            goal.textContent = event.goal;
            metaRow.appendChild(goal);
        }

        const queryBlock = document.createElement("div");
        queryBlock.className = "activity-card__query-block";
        const queryLabel = document.createElement("span");
        queryLabel.className = "activity-card__query-label";
        queryLabel.textContent = "Query";
        const queryText = document.createElement("p");
        queryText.className = "activity-card__query";
        queryText.textContent = event.query || "Working on next query…";
        queryBlock.appendChild(queryLabel);
        queryBlock.appendChild(queryText);

        const resultsList = document.createElement("ul");
        resultsList.className = "activity-card__results";
        if (event.results && event.results.length) {
            event.results.slice(0, 3).forEach((item) => {
                const li = document.createElement("li");
                const title = item.title || "Result";
                const snippet = item.snippet || "";
                if (item.url) {
                    const link = document.createElement("a");
                    link.href = item.url;
                    link.target = "_blank";
                    link.rel = "noopener";
                    link.textContent = title;
                    li.appendChild(link);
                } else {
                    const strong = document.createElement("strong");
                    strong.textContent = title;
                    li.appendChild(strong);
                }
                if (snippet) {
                    const span = document.createElement("span");
                    span.textContent = ` – ${snippet}`;
                    li.appendChild(span);
                }
                resultsList.appendChild(li);
            });
        } else {
            const li = document.createElement("li");
            li.textContent = "Collecting insights…";
            resultsList.appendChild(li);
        }

        card.appendChild(header);
        if (metaRow.childElementCount) {
            card.appendChild(metaRow);
        }
        card.appendChild(queryBlock);
        card.appendChild(resultsList);
        fragment.appendChild(card);
    });

    researchActivityList.innerHTML = "";
    researchActivityList.appendChild(fragment);
};

const renderAgentConsole = () => {
    if (!agentConsole || !agentConsoleList || !workspaceShell) return;
    const researchEntries = buildResearchAgentEntries();
    const strategyEntries = buildStrategyAgentEntries();
    const entries = [...researchEntries, ...strategyEntries];
    const shouldShow = CONSOLE_ACTIVE_STAGES.has(currentStage) && entries.length > 0;

    agentConsole.classList.toggle("hidden", !shouldShow);
    workspaceShell.classList.toggle("workspace--solo", !shouldShow);

    if (!shouldShow) {
        agentConsoleList.innerHTML = "";
        return;
    }

    agentConsoleList.innerHTML = "";
    entries
        .sort((a, b) => statusOrder(a.status) - statusOrder(b.status))
        .forEach((entry) => agentConsoleList.appendChild(buildAgentChip(entry)));
};

const buildResearchAgentEntries = () => {
    if (!latestResearchActivity || !latestResearchActivity.length) {
        return [];
    }
    const latestByAgent = new Map();
    latestResearchActivity.forEach((event) => {
        const key = event.agent || event.channel || event.id;
        if (!key) return;
        latestByAgent.set(key, event);
    });

    const entries = [];
    latestByAgent.forEach((event, key) => {
        entries.push({
            id: key,
            title: event.agent || formatChannelName(event.channel),
            meta: formatAgentSource(event.source),
            detail: formatDetail(event.goal || event.query || `Working ${formatChannelName(event.channel)}`),
            status: normalizeStatus(event.status),
            timestamp: event.completed_at || event.started_at || "",
        });
    });
    return entries;
};

const buildStrategyAgentEntries = () => {
    if (!CONSOLE_ACTIVE_STAGES.has(currentStage) || !latestProgressLog.length) {
        return [];
    }
    const encounteredIndexes = [];
    const normalizedLog = latestProgressLog.map((line) => line.toLowerCase());
    STRATEGY_AGENT_BLUEPRINTS.forEach((slot, index) => {
        if (normalizedLog.some((line) => line.includes(slot.match))) {
            encounteredIndexes.push(index);
        }
    });
    if (!encounteredIndexes.length) {
        return [];
    }

    const latestIndex = Math.max(...encounteredIndexes);
    const planComplete = hasPlan && currentStage !== "analyzing";

    return encounteredIndexes.map((index) => {
        const slot = STRATEGY_AGENT_BLUEPRINTS[index];
        let status = "running";
        if (planComplete || index < latestIndex) {
            status = "complete";
        } else if (index === latestIndex) {
            status = currentStage === "analyzing" ? "running" : "complete";
        }
        return {
            id: `strategy-${slot.key}`,
            title: slot.label,
            meta: "Strategy",
            detail: formatDetail(slot.detail),
            status,
        };
    });
};

const buildAgentChip = ({ title, meta, detail, status }) => {
    const li = document.createElement("li");
    li.className = "agent-chip";

    const indicator = document.createElement("span");
    indicator.className = `agent-chip__indicator agent-chip__indicator--${statusClass(status)}`;

    const body = document.createElement("div");
    body.className = "agent-chip__body";

    const titleRow = document.createElement("div");
    titleRow.className = "agent-chip__title";
    titleRow.textContent = title;

    const metaRow = document.createElement("div");
    metaRow.className = "agent-chip__meta";
    metaRow.textContent = `${meta} • ${statusLabel(status)}`;

    const detailRow = document.createElement("div");
    detailRow.className = "agent-chip__detail";
    detailRow.textContent = detail;

    body.appendChild(titleRow);
    body.appendChild(metaRow);
    body.appendChild(detailRow);

    li.appendChild(indicator);
    li.appendChild(body);
    return li;
};

const statusClass = (status) => {
    if (status === "running") return "running";
    if (status === "complete") return "complete";
    if (status === "error") return "error";
    return "pending";
};

const statusLabel = (status) => {
    if (status === "running") return "Running";
    if (status === "complete") return "Complete";
    if (status === "error") return "Needs attention";
    return "Queued";
};

const statusOrder = (status) => {
    const order = { running: 0, pending: 1, complete: 2, error: 3 };
    return order[status] ?? 2;
};

const normalizeStatus = (status) => {
    if (!status) return "pending";
    const value = String(status).toLowerCase();
    if (["running", "complete", "error"].includes(value)) {
        return value;
    }
    return "pending";
};

const formatDetail = (text = "") => {
    const value = text || "Queued for launch";
    if (value.length > 110) {
        return `${value.slice(0, 107)}…`;
    }
    return value;
};

const formatAgentSource = (text = "") => {
    return text || "Research";
};

const formatChannelName = (channel = "Agent") => {
    return channel
        .toString()
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
};

const statusMessages = {
    planning: "Share a company brief to kick things off.",
    confirming_plan: "Waiting for approval to launch the agents.",
    researching: "Agents are sweeping the open web and news feeds…",
    analyzing: "Strategy agents are building the account plan…",
    reviewing: "Account plan ready—open the Account Plan tab to review.",
};

const updateStatusBanner = (stage) => {
    if (!statusBanner || !statusBannerText) return;
    let message = statusMessages[stage] || "";
    const latest = latestProgressLog[latestProgressLog.length - 1];
    if (latest) {
        message = latest;
    } else if (stage === "reviewing" && hasPlan) {
        message = statusMessages.reviewing;
    }
    if (!message) {
        statusBanner.classList.add("hidden");
        return;
    }
    statusBannerText.textContent = message;
    statusBanner.classList.remove("hidden");
};

const handleProgressPayload = (items = []) => {
    latestProgressLog = items;
    updateProgress(items);
    updateStatusBanner(currentStage);
    renderAgentConsole();
};

const serializeSections = (report) => ({
    overview: report.sections?.overview || "",
    industry: report.sections?.industry || "",
    financials: report.sections?.financials || "",
    talent: report.sections?.talent || "",
    leadership: report.sections?.leadership || "",
    news: report.sections?.news || "",
    swot: report.sections?.swot || "",
    opportunities: report.sections?.opportunities || "",
    strategy: report.sections?.strategy || "",
    plan_30_60_90: report.sections?.plan_30_60_90 || "",
});

const renderPlan = (report) => {
    if (!report || !report.sections) {
        planContainer.innerHTML = "<p>No account plan yet.</p>";
        return;
    }

    const sections = serializeSections(report);
    const fragment = document.createDocumentFragment();
    Object.entries(sections).forEach(([key, value]) => {
        const sectionEl = document.createElement("section");
        sectionEl.className = "plan-section";
        const heading = key.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
        const header = document.createElement("div");
        header.className = "plan-section__header";
        const title = document.createElement("h3");
        title.textContent = heading;
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.section = key;
        button.className = "regen-btn";
        button.textContent = "Regenerate";
        header.appendChild(title);
        header.appendChild(button);

        const body = document.createElement("div");
        body.className = "plan-section__body";
        if (value) {
            body.innerHTML = renderMarkdown(value);
        } else {
            body.innerHTML = "<em>Not generated yet.</em>";
        }

        sectionEl.appendChild(header);
        sectionEl.appendChild(body);
        fragment.appendChild(sectionEl);
    });
    planContainer.innerHTML = "";
    planContainer.appendChild(fragment);

    document.querySelectorAll(".regen-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const section = btn.dataset.section;
            const instruction = window.prompt(
                "Optional additional direction for this section",
                "Focus more on AI expansion in healthcare"
            );
            regenerateSection(section, instruction || "");
        });
    });
};

const renderSources = (sources) => {
    if (!sources || sources.length === 0) {
        sourcesList.innerHTML = "<li>No sources captured yet.</li>";
        return;
    }
    sourcesList.innerHTML = "";
    sources.forEach((source) => {
        const li = document.createElement("li");
        li.innerHTML = `<strong>[${source.type || "web"}]</strong> <a href="${source.url}" target="_blank">${
            source.title || source.url
        }</a>`;
        sourcesList.appendChild(li);
    });
};

const fetchPlan = () => {
    fetch("/api/report")
        .then((res) => res.json())
        .then((data) => {
            renderPlan(data);
            renderSources(data.sources || []);
            const planHasSections = Boolean(data.sections && Object.keys(data.sections).length);
            hasPlan = planHasSections;
            updateStageUI(currentStage, hasPlan);
        });
};

const regenerateSection = (section, instruction) => {
    fetch("/api/regenerate-section", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ section, instruction }),
    })
        .then((res) => {
            if (!res.ok) {
                return res.json().then((data) => Promise.reject(data.error || "Unable to regenerate."));
            }
            return res.json();
        })
        .then((data) => {
            appendMessage("assistant", `Updated ${data.section} (version ${data.version}).`);
            fetchPlan();
        })
        .catch((err) => appendMessage("assistant", err.toString()));
};

const pollProgress = () => {
    fetch("/api/progress")
        .then((res) => res.json())
        .then((data) => {
            handleProgressPayload(data.progress_log || []);
            if (data.research_activity) {
                latestResearchActivity = data.research_activity;
                renderResearchActivity(latestResearchActivity);
                renderAgentConsole();
            }
            updateStageUI(data.stage, hasPlan);
            if (data.stage === "reviewing") {
                fetchPlan();
            }
        })
        .catch(() => {});
};

chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    if (!firstMessageSent) {
        hideHero();
        firstMessageSent = true;
    }
    appendMessage("user", message);
    chatInput.value = "";

    fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
    })
        .then((res) => res.json())
        .then((data) => {
            appendMessage("assistant", data.reply);
            handleProgressPayload(data.progress_log || []);
            if (data.research_activity) {
                latestResearchActivity = data.research_activity;
                renderResearchActivity(latestResearchActivity);
                renderAgentConsole();
            }
            updateStageUI(data.stage, data.has_account_plan || hasPlan);
            if (data.has_account_plan) {
                fetchPlan();
            }
        })
        .catch((error) => {
            console.error(error);
            appendMessage("assistant", "Something went wrong. Please try again.");
        });
});

refreshPlanButton.addEventListener("click", fetchPlan);
downloadPdfButton.addEventListener("click", () => {
    window.open("/api/export-pdf", "_blank");
});

tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
        if (button.disabled || button.classList.contains("disabled")) {
            return;
        }
        const tab = button.dataset.tab;
        if (tab) {
            setActiveTab(tab, true);
            if (tab === "plan" && hasPlan) {
                fetchPlan();
            }
        }
    });
});

setInterval(pollProgress, 4000);

renderAgentConsole();
