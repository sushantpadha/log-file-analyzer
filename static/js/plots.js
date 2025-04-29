import {
	parseDatetimeInputs,
	validateFilterDates,
	setFilterOpts,
	getPlotRequest,
	getPlotStatusRequestURL,
	getPlotURL,
	getMetadataRequestURL,
	setFilterRange,
	fmtTimestamp,
	updateFilterValues,
	resetFilterValues,
} from "./utils.js";

// define elements
const selectEl = document.getElementById('log-select-plot');
const optionsDiv = document.getElementById('plot-options');

const plotDisplayContainer = document.getElementById('plot-display-container');
const loadingMessage = document.getElementById('plot-loading-message');
const errorMessage = document.getElementById('plot-error-message');
const plotDisplayArea = document.getElementById('plot-display-area');

const genPlotsBtn = document.getElementById('generate-plots-btn');
const plotTypeCheckboxes = document.querySelectorAll('input[name="plot_type"]');

const customCheckbox = document.getElementById('plot-custom');
const codeEditorFieldset = document.getElementById('code-editor-controls');

const filterApplyBtn = document.getElementById('filter-apply-btn');
const filterResetBtn = document.getElementById('filter-reset-btn');

let oldSelectedId = selectEl.value;

// ====================== event listeners =======================

document.addEventListener('DOMContentLoaded', () => {
	updateOptionsDiv();
	toggleEditor();

	// initialize code editor via code mirror
	window.codeEditor = CodeMirror.fromTextArea(document.getElementById("code-editor"), {
		mode: "python",
		theme: "default",
		lineNumbers: true,
		indentUnit: 4,
		tabSize: 4,
		lineWrapping: true,
	});
});

selectEl.addEventListener('click', () => {
	// check if new one has been selected
	if (selectEl.value && selectEl.value !== oldSelectedId) {
		oldSelectedId = selectEl.value;
		resetFilterValues();
		updateFilterOptsValues();
	}
	updateOptionsDiv();
});

// buttons and input elements
customCheckbox.addEventListener('change', toggleEditor);

filterApplyBtn.addEventListener('click', filterBtnCallback);

filterResetBtn.addEventListener('click', () => {
	updateFilterOptsValues();
	updateFilterValues(true);
});

genPlotsBtn.addEventListener('click', generatePlots);

// ====================== callbacks functions =======================

function toggleEditor() {
	codeEditorFieldset.style.display = customCheckbox.checked ? 'flex' : 'none';
	// ! force refreshing because codemirror doesn't update the layout
	if (window.codeEditor) {
		window.codeEditor.refresh();
	}
}

// get datetime, validate and set values and update table
function filterBtnCallback() {
	const { startDatetime, endDatetime } = parseDatetimeInputs();

	if (!validateFilterDates(startDatetime, endDatetime)) {
		return;
	}

	setFilterOpts(startDatetime, endDatetime);
}

function updateOptionsDiv() {
	const selectedLogId = selectEl.value;
	if (selectedLogId) {
		optionsDiv.style.display = 'flex';
	} else {
		optionsDiv.style.display = 'none';
		return;
	}

	updateFilterOptsValues();
}

// ====================== plot handling =======================

function generatePlots() {
	// obtain user selected plot types
	const plotOpts = Array.from(plotTypeCheckboxes)
		.filter(node => node.checked)
		.map(node => node.value);

	const selectedLogId = selectEl.value;
	if (!selectedLogId) return;

	// check for custom code option
	const customCode = (plotOpts.includes("custom") && window.codeEditor)
		? window.codeEditor.getValue()
		: null;

	// generate the plot request and reset display containers
	const { endpoint, payload } = getPlotRequest(selectedLogId, plotOpts, customCode);
	plotDisplayArea.innerHTML = '';
	plotDisplayArea.style.display = 'none';
	loadingMessage.style.display = 'none';
	errorMessage.style.display = 'none';

	// send plot request
	sendPlotRequest(endpoint, payload);
}

async function sendPlotRequest(endpoint, payload) {
	try {
		// send the request to the server
		const response = await fetch(endpoint, payload);
		// ! NOTE: here we try to display whatever the server returns to the user
		// if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
		const result = await response.json();
		if (result.error) return showError(`Error loading data: ${result.error}`);

		// poll status
		loadingMessage.style.display = 'block';
		pollPlotStatus();
	} catch (err) {
		showError(`Error generating plots: ${err.message}`);
	}
}

function pollPlotStatus() {
	let attempts = 0;
	// total = 60 * 500ms = 30s
	const maxAttempts = 60;

	const interval = setInterval(async () => {
		attempts++;
		// timeout
		if (attempts >= maxAttempts) {
			clearInterval(interval);
			showError("Error requesting job status file! Request timed out.");
			return;
		}

		try {
			// fetch status
			const response = await fetch(getPlotStatusRequestURL());
			if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
			const result = await response.json();

			if (result.status == 'error') {
				// NOTE: in this case, we terminate on error
				clearInterval(interval);
				showError(`Error in plot gen. / status file I/O: ${result.error}`);
				return;
			}

			if (result.error) {
				// NOTE: in this case, we do not terminate on error
				showError(`Error in plot gen. / status file I/O: ${result.error}`);
			}

			// if done, render plots
			if (result.status === 'done') {
				clearInterval(interval);
				renderPlots(result.plot_files);
			}
		} catch (err) {
			clearInterval(interval);
			showError(`Error fetching plot status: ${err.message}`);
		}
	}, 500);
}

function renderPlots(plotFiles) {
	// reset display containers
	loadingMessage.style.display = 'none';
	plotDisplayArea.innerHTML = '';

	const prettyTitles = {
		'events_over_time': 'Events logged with time (Line)',
		'level_distribution': 'Level State Distribution (Pie)',
		'event_code_distribution': 'Event Code Distribution (Bar)',
		'custom': 'Custom Plot',
	}

	Object.entries(plotFiles).forEach(([type, file]) => {
		// generate plot div
		const plotDiv = document.createElement('div');
		plotDiv.classList.add('plot-container');

		// plot title
		const plotTitle = document.createElement('h3');
		plotTitle.classList.add('plot-title');
		plotTitle.textContent = prettyTitles[type] || type;

		// plot image
		const plotImg = document.createElement('img');
		plotImg.classList.add('plot-image');
		plotImg.src = getPlotURL(file);

		// plot download link
		const plotDLLink = document.createElement('a');
		plotDLLink.classList.add('plot-dl-link', 'fake-btn');
		plotDLLink.textContent = "Download Plot";
		plotDLLink.href = getPlotURL(file, true);
		plotDLLink.download = file;

		plotDiv.appendChild(plotTitle);
		plotDiv.appendChild(plotImg);
		plotDiv.appendChild(plotDLLink);
		plotDisplayArea.appendChild(plotDiv);
	});

	plotDisplayArea.style.display = 'flex';
}

// ===================== helper ========================

// update filter options with provided values
async function updateFilterOptsValues() {
	try {
		const response = await fetch(getMetadataRequestURL(selectEl.value));
		if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

		const result = await response.json();
		if (result.error) {
			showError(`Error loading metadata: ${result.error}`);
			return;
		}

		const start = fmtTimestamp(result.start_timestamp);
		const end = fmtTimestamp(result.end_timestamp);

		console.log(`setting range ${start} ${end}`);

		setFilterRange(start, end);
		setFilterOpts(start, end);
		updateFilterValues();
	} catch (error) {
		showError(`Error loading metadata: ${error.message}`);
	}
}

// helper for error
function showError(message) {
	loadingMessage.style.display = 'none';
	errorMessage.textContent = message;
	errorMessage.style.display = 'block';
	console.error(message);
}
