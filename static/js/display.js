import {
	getCSVRequestURL,
	parseDatetimeInputs,
	validateFilterDates,
	setFilterOpts,
	// getFilterOpts,
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

// ================= add event listeners ============================

document.addEventListener('DOMContentLoaded', updateTable);
selectEl.addEventListener('click', () => {
	updateTable();
	if (selectEl.value && selectEl.value !== oldSelectedId) {
		oldSelectedId = selectEl.value;
		resetFilterValues();
		updateFilterOptsValues();
	}
});
filterApplyBtn.addEventListener('click', filterBtnCallback);

sortResetBtn.addEventListener('click', () => {
	resetSortOpts();
	updateTable(selectEl);
});

filterResetBtn.addEventListener('click', () => {
	updateTable(selectEl);
	updateFilterOptsValues();
	updateFilterValues(true);
});

// =================== eventlistener callback funcs =================

// parse filter data, update date global vars and call `updateTable`
function filterBtnCallback() {
	// parse
	const { startDatetime, endDatetime } = parseDatetimeInputs()

	// validate
	if (!validateFilterDates(startDatetime, endDatetime)) {
		return;
	}

	// set global vars
	setFilterOpts(startDatetime, endDatetime);

	// update table
	updateTable(selectEl);
}

// update the `sortOpts` global var and call `updateTable`
function sortBtnCallback(type, field) {
	// type = +/-
	// field is int from 0 - 4 (inc.)
	const opt = `${type}${field}`;

	setSortOpts(opt);

	// finally, update table
	updateTable(selectEl);
}

// send HTTPRequest via `fetch` and update table
function updateTable() {
	const selectedLogId = selectEl.value;
	// console.log(getRequestURL(selectedLogId));

	// clear table content and remove controls and error messages
	logTable.querySelector('thead').innerHTML = '';
	logTable.querySelector('tbody').innerHTML = '';
	errorMessage.style.display = 'none';
	controlsDiv.style.display = 'none';

	// parse sort opts to highlight buttons
	const parsedSortOpts = getSortOpts();
	// console.log(parsedSortOpts);

	if (!selectedLogId) {
		return
	}
	loadingMessage.style.display = 'block';

	// fetch csv data from backend
	const reqURL = getCSVRequestURL(selectedLogId, false);

	console.log(`Making HTTP request: ${reqURL}`)

	fetch(reqURL)
		.then(response => {
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			return response.json();
		})
		.then(result => {
			// error handling
			loadingMessage.style.display = 'none';
			if (result.error) {
				errorMessage.textContent = `Error loading data: ${result.error}`;
				errorMessage.style.display = 'block';
				return;
			}

			// populate table header
			const thead = logTable.querySelector('thead');
			const headerRow = document.createElement('tr');

			result.header.forEach((colName, colIdx) => {
				const th = document.createElement('th');
				th.textContent = colName;

				// ▲▼ add buttons with appropriate classes and attach event listeners

				const btn1 = document.createElement('button');
				btn1.textContent = '▲';
				btn1.classList.add('btn-sort');
				btn1.classList.add('asc');
				if (parsedSortOpts.includes(`+${colIdx}`))  // set btn to be active if in `parsedSortOpts`
					btn1.classList.add('active');
				btn1.addEventListener('click', (ev) => sortBtnCallback('+', colIdx, ev.currentTarget));
				th.appendChild(btn1)

				const btn2 = document.createElement('button');
				btn2.textContent = '▼';
				btn2.classList.add('btn-sort');
				btn2.classList.add('desc');
				if (parsedSortOpts.includes(`-${colIdx}`))  // set btn to be active if in `parsedSortOpts`
					btn2.classList.add('active');
				btn2.addEventListener('click', (ev) => sortBtnCallback('-', colIdx, ev.currentTarget));
				th.appendChild(btn2)

				headerRow.appendChild(th);
			});
			thead.appendChild(headerRow);

			// populate table body
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

			// set controls and download link
			controlsDiv.style.display = 'block';
			downloadLink.href = getCSVRequestURL(selectedLogId, true);
			downloadLink.download = `${selectedLogId}.csv`;  // default suggestion for filename
			// will be overriden by response from flask app?


		})
		.catch(error => {
			loadingMessage.style.display = 'none';
			errorMessage.textContent = `Error fetching CSV data: ${error}`;
			errorMessage.style.display = 'block';
			console.error('Error fetching CSV:', error);
		});
}

function updateFilterOptsValues() {
	// make call to fetch metadata for updating filtering options
	fetch(getMetadataRequestURL(selectEl.value))
		.then(response => {
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			return response.json();
		})
		.then(result => {
			// error handling
			if (result.error) {
				errorMessage.textContent = `Error loading metadata: ${result.error}`;
				errorMessage.style.display = 'block';
				return;
			}

			// extract formatted timestamps
			const start = fmtTimestamp(result.start_timestamp);
			const end = fmtTimestamp(result.end_timestamp);

			console.log(`setting range ${start} ${end}`)

			// set limits
			setFilterRange(start, end);

			// and defaults
			setFilterOpts(start, end);
			updateFilterValues();
		})
		.catch(error => {
			loadingMessage.style.display = 'none';
			errorMessage.textContent = `Error generating plots / fetching status: ${error}`;
			errorMessage.style.display = 'block';
			console.error('Error generating plots / fetching status:', error);
		});
}
