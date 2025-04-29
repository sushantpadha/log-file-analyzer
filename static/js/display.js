import {
	getCSVRequestURL,
	parseDatetimeInputs,
	validateFilterDates,
	setFilterOpts,
	setSortOpts,
	getSortOpts,
	resetSortOpts,
	resetFilterOpts,
	setFilterRange,
	getDatetimeBoundsFromData,
	updateFilterValues,
	getMetadataRequestURL,
	fmtTimestamp,
	resetFilterValues,
} from "./utils.js";

// define elements
const selectEl = document.getElementById('log-select');
const displayArea = document.getElementById('log-display-area');
const logTable = document.getElementById('log-table');
const loadingMessage = document.getElementById('loading-message');
const errorMessage = document.getElementById('error-message');
const controlsDiv = document.getElementById('controls');
const downloadLink = document.getElementById('download-csv-link');

const sortResetBtn = document.getElementById('sort-reset-btn');
const filterApplyBtn = document.getElementById('filter-apply-btn');
const filterResetBtn = document.getElementById('filter-reset-btn');

let oldSelectedId = selectEl.value;

// ====================== event listeners =======================

document.addEventListener('DOMContentLoaded', () => {
	updateTable();
});

selectEl.addEventListener('click', () => {
	// check if new one has been selected
	if (selectEl.value && selectEl.value !== oldSelectedId) {
		oldSelectedId = selectEl.value;
		resetFilterValues();
		updateFilterOptsValues();
	}
	updateTable();
});

filterApplyBtn.addEventListener('click', filterBtnCallback);

// sort reset
sortResetBtn.addEventListener('click', () => {
	resetSortOpts();
	updateTable();
});

// filter reset
filterResetBtn.addEventListener('click', () => {
	updateTable();
	updateFilterOptsValues();
	updateFilterValues(true);
});

// ====================== callback functions =======================

// get datetime, validate and set values and update table
function filterBtnCallback() {
	const { startDatetime, endDatetime } = parseDatetimeInputs();

	if (!validateFilterDates(startDatetime, endDatetime)) {
		return;
	}

	setFilterOpts(startDatetime, endDatetime);
	updateTable();
}

function sortBtnCallback(type, field) {
	const opt = `${type}${field}`;
	setSortOpts(opt);
	updateTable();
}

// ====================== table handling =======================

async function updateTable() {
	const selectedLogId = selectEl.value;

	// reset elements
	logTable.querySelector('thead').innerHTML = '';
	logTable.querySelector('tbody').innerHTML = '';
	errorMessage.style.display = 'none';
	controlsDiv.style.display = 'none';

	const parsedSortOpts = getSortOpts();

	if (!selectedLogId) return;

	loadingMessage.style.display = 'block';

	const reqURL = getCSVRequestURL(selectedLogId, false);
	console.log(`Making HTTP request: ${reqURL}`);

	// make new request for csv data
	try {
		const response = await fetch(reqURL);
		if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
		const result = await response.json();

		if (result.error) return showError(`Error loading data: ${result.error}`);

		// populate header
		const thead = logTable.querySelector('thead');
		const headerRow = document.createElement('tr');

		result.header.forEach((colName, colIdx) => {
			// th element
			const th = document.createElement('th');
			th.textContent = colName;

			// add sort buttons
			const btn1 = document.createElement('button');
			btn1.textContent = '▲';
			btn1.classList.add('btn-sort', 'asc');
			if (parsedSortOpts.includes(`+${colIdx}`)) btn1.classList.add('active');
			btn1.addEventListener('click', (ev) => sortBtnCallback('+', colIdx, ev.currentTarget));
			th.appendChild(btn1);

			const btn2 = document.createElement('button');
			btn2.textContent = '▼';
			btn2.classList.add('btn-sort', 'desc');
			if (parsedSortOpts.includes(`-${colIdx}`)) btn2.classList.add('active');
			btn2.addEventListener('click', (ev) => sortBtnCallback('-', colIdx, ev.currentTarget));
			th.appendChild(btn2);

			headerRow.appendChild(th);
		});
		thead.appendChild(headerRow);

		// populate body
		const tbody = logTable.querySelector('tbody');
		result.data.forEach(rowData => {
			const tr = document.createElement('tr');
			rowData.forEach(cellData => {
				const td = document.createElement('td');
				td.textContent = cellData;
				tr.appendChild(td);
			});
			tbody.appendChild(tr);
		});

		// display controls
		controlsDiv.style.display = 'flex';
		downloadLink.href = getCSVRequestURL(selectedLogId, true);
		downloadLink.download = `${selectedLogId}.csv`;
	}
	catch (err) {
		showError(`Error fetching CSV data: ${err.message}`);
	}
	loadingMessage.style.display = 'none';
}

// ===================== helper ========================

// update filter options with provided values
async function updateFilterOptsValues() {
	try {
		const response = await fetch(getMetadataRequestURL(selectEl.value));
		if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
		const result = await response.json();

		if (result.error) return showError(`Error loading metadata: ${result.error}`);

		const start = fmtTimestamp(result.start_timestamp);
		const end = fmtTimestamp(result.end_timestamp);

		console.log(`setting range ${start} ${end}`);

		setFilterRange(start, end);
		setFilterOpts(start, end);
		updateFilterValues();
		console.log(`Filter options updated: ${start} - ${end}`);
	}
	catch (err) {
		showError(`Error generating plots / fetching status: ${err.message}`);
	}
}

// helper for error
function showError(message) {
	loadingMessage.style.display = 'none';
	errorMessage.textContent = message;
	errorMessage.style.display = 'block';
	console.error(message);
}