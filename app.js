document.addEventListener("DOMContentLoaded", () => {
    // --- Mockup Tab Switching ---
    const tabBse = document.getElementById("mock-tab-bse");
    const tabNse = document.getElementById("mock-tab-nse");
    const pageBse = document.getElementById("mock-page-bse");
    const pageNse = document.getElementById("mock-page-nse");
    const runBtn = document.getElementById("mock-run-btn");
    const runBtnText = document.getElementById("mock-run-btn-text");

    let currentExchange = "BSE";

    function switchExchange(exchange) {
        currentExchange = exchange;
        if (exchange === "BSE") {
            tabBse.classList.add("active");
            tabBse.classList.remove("inactive");
            tabNse.classList.add("inactive");
            tabNse.classList.remove("active");
            
            pageBse.classList.add("active");
            pageNse.classList.remove("active");
            
            runBtnText.textContent = "START BSE DOWNLOAD & RUN EXTRACTOR";
        } else {
            tabNse.classList.add("active");
            tabNse.classList.remove("inactive");
            tabBse.classList.add("inactive");
            tabBse.classList.remove("active");
            
            pageNse.classList.add("active");
            pageBse.classList.remove("active");
            
            runBtnText.textContent = "START NSE DOWNLOAD & RUN API SUITE";
        }
    }

    tabBse.addEventListener("click", () => switchExchange("BSE"));
    tabNse.addEventListener("click", () => switchExchange("NSE"));

    // --- Mockup Theme Toggling (Aluminium vs Carbon) ---
    const themeToggleBtn = document.getElementById("web-theme-toggle");
    const appMockup = document.getElementById("app-mockup");

    themeToggleBtn.addEventListener("click", () => {
        if (appMockup.classList.contains("theme-carbon")) {
            appMockup.classList.remove("theme-carbon");
            appMockup.classList.add("theme-aluminium");
        } else {
            appMockup.classList.remove("theme-aluminium");
            appMockup.classList.add("theme-carbon");
        }
    });

    // --- Interactive Terminal Logger Simulation ---
    const terminalScreen = document.getElementById("mock-terminal-screen");
    const statusTag = document.getElementById("mock-status");
    const simBseBtn = document.getElementById("sim-bse-btn");
    const simNseBtn = document.getElementById("sim-nse-btn");
    const simClearBtn = document.getElementById("sim-clear-btn");

    let simulationTimeoutIds = [];
    let isRunningSimulation = false;

    function clearSimulation() {
        simulationTimeoutIds.forEach(id => clearTimeout(id));
        simulationTimeoutIds = [];
        isRunningSimulation = false;
        
        // Restore run button
        runBtn.className = "mockup-run-btn green-btn";
        runBtn.disabled = false;
        if (currentExchange === "BSE") {
            runBtnText.textContent = "START BSE DOWNLOAD & RUN EXTRACTOR";
        } else {
            runBtnText.textContent = "START NSE DOWNLOAD & RUN API SUITE";
        }
    }

    function writeTerminalLine(text, append = true) {
        if (append) {
            terminalScreen.innerHTML += "<br>" + text;
        } else {
            terminalScreen.innerHTML = text;
        }
        // Auto scroll terminal container
        const glass = terminalScreen.parentElement;
        glass.scrollTop = glass.scrollHeight;
    }

    function setMockStatus(status, className = "") {
        statusTag.textContent = "● " + status;
        statusTag.className = "mockup-status-tag " + className;
    }

    // BSE Downloader Mock Log Sequence
    const bseLogSequence = [
        { delay: 100, log: "=========================================================" },
        { delay: 400, log: "[10:24:02] Launching BSE Extranet Downloader Process..." },
        { delay: 700, log: "[10:24:02] Target Folder: EQ / Transaction" },
        { delay: 1000, log: "[10:24:03] Save Path verified: C:\\Users\\Broker\\Desktop\\downloads\\" },
        { delay: 1400, log: "[10:24:03] Initializing headless browser engine..." },
        { delay: 2000, log: "[10:24:05] Navigating to https://member.bseindia.com/..." },
        { delay: 2600, log: "[10:24:07] Extranet portal loaded. Solving login Captcha..." },
        { delay: 3400, log: "[10:24:09] Captcha image extracted. Invoking PyTorch solver..." },
        { delay: 4200, log: "[10:24:10] Solver response: [9x4H2]. Submitting credentials..." },
        { delay: 5000, log: "[10:24:12] Login successful! Entering EQ/Transaction directory..." },
        { delay: 5700, log: "[10:24:14] Found 3 files for Extraction Date 15-06-2026." },
        { delay: 6300, log: "[10:24:15] Downloading file 1/3: C0260615.zip (240 KB)..." },
        { delay: 7000, log: "[10:24:17] Downloading file 2/3: P0260615.zip (1.2 MB)..." },
        { delay: 7700, log: "[10:24:19] Downloading file 3/3: T0260615.zip (80 KB)..." },
        { delay: 8300, log: "[10:24:20] Extraction complete. Closing browser hooks." },
        { delay: 9000, log: ">>> BSE DOWNLOAD RUN COMPLETED SUCCESSFULLY! <<<" }
    ];

    // NSE API Downloader Mock Log Sequence
    const nseLogSequence = [
        { delay: 100, log: "=========================================================" },
        { delay: 400, log: "[10:24:40] Launching NSE Extranet Downloader Process..." },
        { delay: 800, log: "[10:24:41] Target Path: C:\\Users\\Broker\\Desktop\\test_nse\\" },
        { delay: 1200, log: "[10:24:41] Pre-checked segments: Cash (CM), Derivatives (FO), Currency (CD)" },
        { delay: 1600, log: "[10:24:42] ---------------------------------------------------------" },
        { delay: 2000, log: "[10:24:42] STARTING NSE CASH MARKET (CM) DOWNLOAD..." },
        { delay: 2400, log: "[10:24:43] Requesting Login URL (version 2.0)..." },
        { delay: 3000, log: "[10:24:45] API Session Authenticated. Downloading common bhavcopy..." },
        { delay: 3500, log: "[10:24:46] File saved: test_nse\\CASH\\bhavcopy_15062026.csv" },
        { delay: 4000, log: "[10:24:47] ---------------------------------------------------------" },
        { delay: 4400, log: "[10:24:47] STARTING NSE FUTURES & OPTIONS (FO) DOWNLOAD..." },
        { delay: 4900, log: "[10:24:49] Fetching member standard reports..." },
        { delay: 5500, log: "[10:24:50] File saved: test_nse\\NSEFO\\FO_Report_15062026.zip" },
        { delay: 6000, log: "[10:24:51] ---------------------------------------------------------" },
        { delay: 6400, log: "[10:24:51] STARTING NSE CURRENCY DERIVATIVES (CD) DOWNLOAD..." },
        { delay: 7000, log: "[10:24:53] Fetching clearing files..." },
        { delay: 7600, log: "[10:24:54] File saved: test_nse\\NSECD\\CD_Clearing_15062026.csv" },
        { delay: 8100, log: "[10:24:55] Logging out NSE API Session safely..." },
        { delay: 8600, log: ">>> NSE DOWNLOAD RUN COMPLETED SUCCESSFULLY! <<<" }
    ];

    function runSimulation(exchange) {
        if (isRunningSimulation) {
            clearSimulation();
        }

        isRunningSimulation = true;
        setMockStatus("RUNNING", "running");
        writeTerminalLine("Initializing mock run...", false);

        // Update active GUI tab to match simulation
        switchExchange(exchange);

        // Update run button appearance during execution
        runBtn.className = "mockup-run-btn red-btn";
        runBtn.disabled = true;
        runBtnText.textContent = "SIMULATION RUNNING...";

        const logSeq = exchange === "BSE" ? bseLogSequence : nseLogSequence;

        logSeq.forEach(item => {
            const timeoutId = setTimeout(() => {
                writeTerminalLine(item.log);
                
                // If it is the last item
                if (item === logSeq[logSeq.length - 1]) {
                    setMockStatus("SUCCESS", "success");
                    isRunningSimulation = false;
                    runBtn.className = "mockup-run-btn green-btn";
                    runBtn.disabled = false;
                    if (currentExchange === "BSE") {
                        runBtnText.textContent = "START BSE DOWNLOAD & RUN EXTRACTOR";
                    } else {
                        runBtnText.textContent = "START NSE DOWNLOAD & RUN API SUITE";
                    }
                }
            }, item.delay);
            simulationTimeoutIds.push(timeoutId);
        });
    }

    // Bind Simulation Buttons
    simBseBtn.addEventListener("click", () => runSimulation("BSE"));
    simNseBtn.addEventListener("click", () => runSimulation("NSE"));

    simClearBtn.addEventListener("click", () => {
        clearSimulation();
        terminalScreen.innerHTML = "Console Screen cleared. Waiting for simulation trigger...";
        setMockStatus("IDLE");
    });

    // Also bind the mockup's run button directly to trigger the simulation!
    runBtn.addEventListener("click", () => {
        if (!isRunningSimulation) {
            runSimulation(currentExchange);
        }
    });
});
