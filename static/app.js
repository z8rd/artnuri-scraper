// Global State Variables
let isScraping = false;
let scrapedResults = [];
let pollInterval = null;
let currentKeywords = ["음악", "클래식", "작곡", "미디어아트"];
let selectedState = ""; // Current active status filter
let deadlineSortOrder = "asc"; // Current deadline sort order ('asc' or 'desc')

// Unique Client Session ID for Multi-user isolation
const clientId = getOrCreateClientId();

function getOrCreateClientId() {
    let id = localStorage.getItem("artnuri_client_id");
    if (!id) {
        id = 'client_' + Math.random().toString(36).substring(2, 15);
        localStorage.setItem("artnuri_client_id", id);
    }
    return id;
}

// DOM Elements
const startBtn = document.getElementById("start-btn");
const keywordsInput = document.getElementById("keywords-input");
const globalStatusBadge = document.getElementById("global-status-badge");
const statTime = document.getElementById("stat-time");
const statFound = document.getElementById("stat-found");
const statScraped = document.getElementById("stat-scraped");
const globalProgressBar = document.getElementById("global-progress-bar");
const agentsGrid = document.getElementById("agents-grid");
const resultsTbody = document.getElementById("results-tbody");
const deleteDataBtn = document.getElementById("delete-data");
const sortDeadlineCol = document.getElementById("sort-deadline-col");
const sortIcon = document.getElementById("sort-icon");

// Filter elements
const searchInput = document.getElementById("search-input");
const keywordFilter = document.getElementById("keyword-filter");

// Export elements
const exportExcelBtn = document.getElementById("export-excel");

// Modal elements
const detailsModal = document.getElementById("details-modal");
const modalCloseBtn = document.getElementById("modal-close-btn");
const modalTitle = document.getElementById("modal-title");
const modalHost = document.getElementById("modal-host");
const modalTarget = document.getElementById("modal-target");
const modalRegion = document.getElementById("modal-region");
const modalPeriod = document.getElementById("modal-period");
const modalBusinessType = document.getElementById("modal-business-type");
const modalGenre = document.getElementById("modal-genre");
const modalViews = document.getElementById("modal-views");
const modalSourceSite = document.getElementById("modal-source-site");
const modalApplyLink = document.getElementById("modal-apply-link");
const modalOriginalLink = document.getElementById("modal-original-link");
const modalFiles = document.getElementById("modal-files");
const modalDesc = document.getElementById("modal-desc");
const modalContactName = document.getElementById("modal-contact-name");
const modalContactPhone = document.getElementById("modal-contact-phone");

// Page Initialization
document.addEventListener("DOMContentLoaded", () => {

    // Initial fetch to load previous results if they exist
    fetchResults();
    
    // Check current running status on load
    checkStatus();
    
    // Setup Event Listeners
    startBtn.addEventListener("click", handleStartScrape);
    
    // Local Filter listeners
    searchInput.addEventListener("input", filterAndRenderTable);
    keywordFilter.addEventListener("change", filterAndRenderTable);

    
    // Status Tabs Filter listeners
    const tabButtons = document.querySelectorAll("#status-tabs .tab-btn");
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            tabButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            selectedState = btn.getAttribute("data-state");
            filterAndRenderTable();
        });
    });
    
    // Export listeners
    if (exportExcelBtn) exportExcelBtn.addEventListener("click", exportData);
    if (deleteDataBtn) deleteDataBtn.addEventListener("click", handleDeleteData);
    
    // Sort Deadline Listener
    if (sortDeadlineCol) {
        sortDeadlineCol.addEventListener("click", () => {
            if (deadlineSortOrder === "asc") {
                deadlineSortOrder = "desc";
                if (sortIcon) {
                    sortIcon.className = "fa-solid fa-sort-down";
                    sortIcon.style.color = "var(--primary)";
                }
            } else {
                deadlineSortOrder = "asc";
                if (sortIcon) {
                    sortIcon.className = "fa-solid fa-sort-up";
                    sortIcon.style.color = "var(--primary)";
                }
            }
            filterAndRenderTable();
        });
    }
    
    // Modal Close
    modalCloseBtn.addEventListener("click", closeModal);
    window.addEventListener("click", (e) => {
        if (e.target === detailsModal) closeModal();
    });
});

// Start Scraping Handler
async function handleStartScrape() {
    if (isScraping) return;
    
    const kvsRaw = keywordsInput.value.trim();
    if (!kvsRaw) {
        alert("최소 한 개의 키워드를 입력해 주세요.");
        return;
    }
    
    const keywords = kvsRaw.split(",").map(k => k.trim()).filter(k => k.length > 0);
    currentKeywords = keywords;
    
    
    
    // Update UI status to trigger start
    startBtn.disabled = true;
    startBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> 검색기 기동 중...`;
    
    try {
        // Construct query parameters for FastAPI
        const queryParams = keywords.map(kw => `keywords=${encodeURIComponent(kw)}`).join("&");
        const response = await fetch(`/api/scrape?client_id=${clientId}&${queryParams}`, {
            method: "POST"
        });
        
        
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "수집 시작 실패");
        }
        
        isScraping = true;
        updateStatusBadge("running", "수집 기동 중");
        
        // Start Polling
        startPolling();
        
    } catch (e) {
        alert(`에러 발생: ${e.message}`);
        resetStartButton();
    }
}

// Start Polling Status
function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    
    pollInterval = setInterval(checkStatus, 1000);
}

// Stop Polling Status
function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// Check status API
async function checkStatus() {
    
    try {
        const response = await fetch(`/api/status?client_id=${clientId}`);
        if (!response.ok) return;
        
        const data = await response.json();
        updateUI(data);
        
    } catch (e) {
        console.error("Error checking status:", e);
    }
}

// Reset Start Button UI
function resetStartButton() {
    startBtn.disabled = false;
    startBtn.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i> 지원사업 검색`;
}

// Update UI elements based on API status response
function updateUI(data) {
    const status = data.status; // 대기 중, 수집 중, 완료, 오류
    
    statTime.innerText = `${data.elapsed_time}s`;
    statFound.innerText = data.total_found;
    statScraped.innerText = data.total_scraped;
    
    // Update global progress bar
    if (data.total_found > 0) {
        const progressPercent = Math.min(100, Math.round((data.total_scraped / data.total_found) * 100));
        globalProgressBar.style.width = `${progressPercent}%`;
    } else {
        globalProgressBar.style.width = "0%";
    }
    
    // Draw Sub-Agent Cards
    renderAgentCards(data.agents);
    
    if (status === "수집 중") {
        isScraping = true;
        startBtn.disabled = true;
        startBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> 지원사업 검색 중...`;
        updateStatusBadge("running", "병렬 수집 진행 중");
        
        // Ensure polling is running
        if (!pollInterval) startPolling();
        
    } else if (status === "완료") {
        if (isScraping) {
            // Just finished
            isScraping = false;
            resetStartButton();
            stopPolling();
            updateStatusBadge("completed", "수집 완료");
            fetchResults(); // Refresh table
        } else {
            updateStatusBadge("completed", "수집 완료");
        }
        
    } else if (status.startsWith("오류")) {
        isScraping = false;
        resetStartButton();
        stopPolling();
        updateStatusBadge("error", `오류: ${status}`);
        
    } else {
        // 대기 중 (idle)
        isScraping = false;
        resetStartButton();
        stopPolling();
        updateStatusBadge("idle", "서비스 대기 중");
    }
}

// Update Header Status Badge
function updateStatusBadge(type, text) {
    globalStatusBadge.className = `global-status-badge`;
    const dot = globalStatusBadge.querySelector(".status-dot");
    const txt = globalStatusBadge.querySelector(".status-txt");
    
    dot.className = `status-dot ${type}`;
    txt.innerText = text;
}

// Render Sub-Agent Grid Cards
function renderAgentCards(agents) {
    const keys = Object.keys(agents);
    if (keys.length === 0) {
        agentsGrid.innerHTML = `
            <div class="no-agents-placeholder">
                <i class="fa-solid fa-robot"></i>
                <p>수집을 시작하면 검색 결과 카드들이 이곳에 활성화됩니다.</p>
            </div>
        `;
        return;
    }
    
    let html = "";
    keys.forEach(kw => {
        const info = agents[kw];
        const status = info.status;
        
        let badgeClass = "wait";
        let statusLabel = "대기";
        
        if (status === "수집 중" || status === "상세 정보 스크랩 중" || status === "목록 수집 중 (페이징)") {
            badgeClass = "run";
            statusLabel = "수집중";
        } else if (status === "수집 완료" || status === "완료") {
            badgeClass = "done";
            statusLabel = "완료";
        } else if (status.startsWith("오류") || status.startsWith("검색 오류")) {
            badgeClass = "fail";
            statusLabel = "실패";
        }
        
        html += `
            <div class="agent-card ${statusLabel === "수집중" ? "running" : ""}">
                <div class="agent-card-header">
                    <span class="agent-name"><i class="fa-solid fa-robot"></i> ${kw}</span>
                    <span class="agent-status-badge ${badgeClass}">${statusLabel}</span>
                </div>
                <div class="agent-details">
                    <div class="agent-detail-row">
                        <span>현재 상태:</span>
                        <strong style="color: var(--txt-main);">${status}</strong>
                    </div>
                    <div class="agent-detail-row">
                        <span>진행 페이지:</span>
                        <span>${info.current_page} / ${info.total_pages}</span>
                    </div>
                    <div class="agent-detail-row">
                        <span>스크랩 개수:</span>
                        <span>${info.processed_items} / ${info.total_items}건</span>
                    </div>
                </div>
                <div class="agent-progress-box">
                    <div class="agent-progress-header">
                        <span>진행률</span>
                        <span>${info.progress_percentage}%</span>
                    </div>
                    <div class="agent-progress-bar-container">
                        <div class="agent-progress-bar" style="width: ${info.progress_percentage}%;"></div>
                    </div>
                </div>
            </div>
        `;
    });
    
    agentsGrid.innerHTML = html;
}

// Fetch results data from API
async function fetchResults() {
    
    try {
        const response = await fetch(`/api/results?client_id=${clientId}`);
        
        
        if (!response.ok) return;
        
        scrapedResults = await response.json();
        
        // Populate filter options dynamically
        populateKeywordFilter();
        
        // Render Table
        filterAndRenderTable();
        
        // Enable/Disable export buttons
        if (scrapedResults.length > 0) {
            if (exportExcelBtn) exportExcelBtn.disabled = false;
            if (deleteDataBtn) deleteDataBtn.disabled = false;
        } else {
            if (exportExcelBtn) exportExcelBtn.disabled = true;
            if (deleteDataBtn) deleteDataBtn.disabled = true;
        }
        
    } catch (e) {
        console.error("Error fetching results:", e);
    }
}

// Populate matched keywords in filter options
function populateKeywordFilter() {
    const keywordsSet = new Set();
    scrapedResults.forEach(item => {
        const kws = item.matched_keywords || [];
        kws.forEach(k => keywordsSet.add(k));
    });
    
    // Save current selected value
    const currentVal = keywordFilter.value;
    
    let html = '<option value="">모든 키워드</option>';
    Array.from(keywordsSet).sort().forEach(kw => {
        html += `<option value="${kw}">${kw}</option>`;
    });
    keywordFilter.innerHTML = html;
    
    // Restore selection
    keywordFilter.value = currentVal;
}

// Client-side filtering & Render Table Rows
function filterAndRenderTable() {
    const query = searchInput.value.trim().toLowerCase();
    const selectedKw = keywordFilter.value;
    
    const filtered = scrapedResults.filter(item => {
        // Search text filter
        if (query) {
            const title = (item.title || "").toLowerCase();
            const host = (item.host || "").toLowerCase();
            const desc = (item.description || "").toLowerCase();
            if (!title.includes(query) && !host.includes(query) && !desc.includes(query)) {
                return false;
            }
        }
        
        // Keyword filter
        if (selectedKw) {
            const kws = item.matched_keywords || [];
            if (!kws.includes(selectedKw)) return false;
        }
        
        // State filter
        if (selectedState) {
            if (item.state !== selectedState) return false;
        }
        
        return true;
    });
    
    // Sort by deadline
    if (deadlineSortOrder) {
        filtered.sort((a, b) => {
            const dateA = a.deadline || "9999-12-31";
            const dateB = b.deadline || "9999-12-31";
            if (deadlineSortOrder === "asc") {
                return dateA.localeCompare(dateB);
            } else {
                return dateB.localeCompare(dateA);
            }
        });
    }
    
    renderTableRows(filtered);
}

// Render filtered rows into Table
function renderTableRows(items) {
    if (items.length === 0) {
        resultsTbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-table-msg">
                    <i class="fa-solid fa-circle-info"></i> 조건에 맞는 수집 결과 데이터가 없습니다.
                </td>
            </tr>
        `;
        return;
    }
    
    let html = "";
    items.forEach(item => {
        // Build state badge
        let stateBadgeHtml = "";
        if (item.state === "진행중") {
            stateBadgeHtml = `<span class="badge badge-state state-prog">진행중</span>`;
        } else if (item.state === "예정") {
            stateBadgeHtml = `<span class="badge badge-state state-wait">예정</span>`;
        } else {
            stateBadgeHtml = `<span class="badge badge-state state-done">${item.state || "마감"}</span>`;
        }
        
        // Build keywords badges
        const kwBadges = (item.matched_keywords || []).map(kw => 
            `<span class="badge badge-tag">${kw}</span>`
        ).join("");
        
        // Format genre
        const genreText = item.genre || "-";
        
        html += `
            <tr>
                <td><strong>${genreText}</strong></td>
                <td>${kwBadges}</td>
                <td>${stateBadgeHtml}</td>
                <td class="table-title-cell" title="${item.title}">${item.title}</td>
                <td>${item.host || item.source_site || "-"}</td>
                <td style="font-family: var(--font-outfit);">${item.deadline || "-"}</td>
                <td style="text-align: center;">
                    <button class="detail-trigger-btn" onclick="openDetails('${item.docid}')">
                        <i class="fa-solid fa-magnifying-glass-plus"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    resultsTbody.innerHTML = html;
}

// Open Details Modal
function openDetails(docid) {
    const item = scrapedResults.find(x => x.docid === docid);
    if (!item) return;
    
    modalTitle.innerText = item.title || "지원사업 상세 정보";
    modalHost.innerText = item.host || "-";
    modalTarget.innerText = item.target || "-";
    modalRegion.innerText = item.region || "-";
    modalPeriod.innerText = item.period || "-";
    modalBusinessType.innerText = item.business_type || "-";
    modalGenre.innerText = item.genre || "-";
    modalViews.innerText = item.views || "0";
    modalSourceSite.innerText = item.source_site || "-";
    
    // Configure apply link
    if (item.apply_link) {
        modalApplyLink.href = item.apply_link;
        modalApplyLink.style.display = "inline-flex";
    } else {
        modalApplyLink.style.display = "none";
    }
    
    // Configure original link
    modalOriginalLink.href = item.original_url || "#";
    
    // Populate attached files
    const files = item.files || [];
    if (files.length === 0) {
        modalFiles.innerHTML = `<li style="color: var(--txt-muted); font-size:12px;">첨부파일이 없습니다.</li>`;
    } else {
        let filesHtml = "";
        files.forEach(file => {
            filesHtml += `
                <li>
                    <a href="${file.url}" target="_blank">
                        <i class="fa-solid fa-download"></i> ${file.name}
                    </a>
                </li>
            `;
        });
        modalFiles.innerHTML = filesHtml;
    }
    
    // Description text
    modalDesc.innerText = item.description || "본문 상세 정보 내용이 제공되지 않습니다.";
    
    // Inquiry Info
    modalContactName.innerText = item.contact_name || "-";
    modalContactPhone.innerText = item.contact_phone || "-";
    
    // Open Modal
    detailsModal.classList.add("open");
}

// Close Modal
function closeModal() {
    detailsModal.classList.remove("open");
}

// Export Data API trigger (Excel download)
function exportData() {
    window.location.href = `/api/export?client_id=${clientId}`;
}


// Delete Data API trigger
async function handleDeleteData() {
    
    
    const confirmDelete = confirm("서버에 일시 저장된 회원님의 수집 결과 데이터가 모두 영구 삭제됩니다.\n계속하시겠습니까?");
    if (!confirmDelete) return;
    
    try {
        const response = await fetch(`/api/results?client_id=${clientId}`, {
            method: "DELETE"
        });
        
        
        
        if (response.ok) {
            alert("서버에 저장된 데이터가 안전하게 삭제되었습니다.");
            scrapedResults = [];
            filterAndRenderTable();
            if (deleteDataBtn) deleteDataBtn.disabled = true;
            if (exportExcelBtn) exportExcelBtn.disabled = true;
        } else {
            const err = await response.json();
            alert(`데이터 삭제 실패: ${err.detail || "오류"}`);
        }
    } catch (e) {
        alert(`에러 발생: ${e.message}`);
    }
}
