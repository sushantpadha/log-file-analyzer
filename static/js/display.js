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

const startDateEl = document.getElementById('start-date');
const startTimeEl = document.getElementById('start-time');
const endDateEl = document.getElementById('end-date');
const endTimeEl = document.getElementById('end-time');

// global variables for setting parameters for fetch request
let sortOpts = "";
let startDatetimeOpt = ""
let endDatetimeOpt = ""

// these are set from unfiltered csv and used for validating filter options
let minDatetimeOpt = startDatetimeOpt;
let maxDatetimeOpt = endDatetimeOpt;

document.addEventListener('DOMContentLoaded', updateTable);
selectEl.addEventListener('click', updateTable);
filterApplyBtn.addEventListener('click', filterBtnCallback);

sortResetBtn.addEventListener('click', () => {
	sortOpts = "";
	updateTable(selectEl);
});

filterResetBtn.addEventListener('click', () => {
	startDatetimeOpt = "";
	endDatetimeOpt = "";
	updateTable(selectEl);
});

// =================== eventlistener callback funcs =================

// parse filter data, update date global vars and call `updateTable`
function filterBtnCallback() {
	// read data from inputs
	const startDate = startDateEl.value;
	const startTime = startTimeEl.value;
	const endDate = endDateEl.value;
	const endTime = endTimeEl.value;

	// validate data
	if (!(startDate && startTime && endDate && endTime)) {
		console.log(`'${startDate}' '${startTime}' '${endDate}' '${endTime}' `)
		window.alert('One of the date time fields for filtering is empty!');
		return;
	}

	// assuming formats are correct because these are standard HTML elements
	// YYYY-mm-DD and HH:MM:SS resp.

	const startDatetime = `${startDate} ${startTime}`;
	const endDatetime = `${endDate} ${endTime}`;

	// YYYY-mm-DD HH:MM:SS is already in valid lexico order !!!
	if (startDatetime < minDatetimeOpt) {
		window.alert(`Start date time is less than minimum value in log file (${minDatetimeOpt})!`);
		return;
	}
	if (endDatetime > maxDatetimeOpt) {
		window.alert(`End date time is more than maximum value in log file (${maxDatetimeOpt})!`);
		return;
	}
	// basic check
	if (startDatetime > endDatetime) {
		window.alert('Start date time is more than end date time!');
		return;
	}

	// set dates
	startDatetimeOpt = startDatetime;
	endDatetimeOpt = endDatetime;

	// update table
	updateTable(selectEl);
}

// update the `sortOpts` global var and call `updateTable`
function sortBtnCallback(type, field, el) {
	// type = +/-
	// field is int from 0 - 4 (inc.)
	const opt = `${type}${field}`;

	// console.log(`button ${el} clicked with ${opt}`)
	// console.log(`prev opts: ${sort_opts}`)

	// remove prev occurence of any options for this field
	const opts = sortOpts && sortOpts !== ''
		? sortOpts.split(',').filter(o => Number(o.charAt(1)) !== field)
		: [];

	// console.log(`proc opts: ${opts}`)

	sortOpts = [opt, ...opts].join(',');

	// console.log(`new opts: ${sort_opts}`)

	// finally, update table
	updateTable(selectEl);
}

// send HTTPRequest via `fetch` and update table
function updateTable() {
	const selectedLogId = selectEl.value;
	// console.log(getRequestEndpoint(selectedLogId));

	// clear table content and remove controls and error messages
	logTable.querySelector('thead').innerHTML = '';
	logTable.querySelector('tbody').innerHTML = '';
	errorMessage.style.display = 'none';
	controlsDiv.style.display = 'none';

	// parse sort_opts to highlight buttons
	const parsedSortOpts = sortOpts.split(',');
	// console.log(parsedSortOpts);

	if (selectedLogId) {
		loadingMessage.style.display = 'block';

		// fetch csv data from backend
		const reqEndpt = getRequestURL(selectedLogId, 'get_csv');

		console.log(`Making HTTP request: ${reqEndpt}`)
		
		fetch(reqEndpt)
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
				downloadLink.href = getRequestURL(selectedLogId, 'download_csv');
				downloadLink.download = `${selectedLogId}.csv`;  // default suggestion for filename
				// will be overriden by response from flask app?

				// if data is unfiltered, use it to set min and max for date time
				if (!result.filtered) {
					// convert into formatted timestampts YYYY-mm-DD HH:MM:SS
					const fmtdTimestamps = result.data.map(row => row[1]).map(tstmp => {
						const [_, mo, dt, time, yr] = tstmp.split(' ');

						// define month map
						const month_map = {
							"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
							"Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
						};
						const month = month_map[mo];

						return `${yr}-${month}-${dt} ${time}`;
					});

					console.log("setting min max datetimes");

					// use lexi ordering with `reduce` to get min and max
					minDatetimeOpt = fmtdTimestamps.reduce((minm, curr) => (curr < minm ? curr : minm));
					maxDatetimeOpt = fmtdTimestamps.reduce((maxm, curr) => (curr > maxm ? curr : maxm));

					// set limits for input elemets
					startDateEl.min = minDatetimeOpt.split(' ')[0];
					startDateEl.max = maxDatetimeOpt.split(' ')[0];
					startTimeEl.min = minDatetimeOpt.split(' ')[1];
					startTimeEl.max = maxDatetimeOpt.split(' ')[1];

					endDateEl.min = minDatetimeOpt.split(' ')[0];
					endDateEl.max = maxDatetimeOpt.split(' ')[0];
					endTimeEl.min = minDatetimeOpt.split(' ')[1];
					endTimeEl.max = maxDatetimeOpt.split(' ')[1];

					// set defaults
					startDateEl.value = minDatetimeOpt.split(' ')[0];
					startTimeEl.value = minDatetimeOpt.split(' ')[1];

					endDateEl.value = maxDatetimeOpt.split(' ')[0];
					endTimeEl.value = maxDatetimeOpt.split(' ')[1];
				}

			})
			.catch(error => {
				loadingMessage.style.display = 'none';
				errorMessage.textContent = `Error fetching CSV data: ${error}`;
				errorMessage.style.display = 'block';
				console.error('Error fetching CSV:', error);
			});
	}
}

// ========================== helper funcs ==========================

// returns the full request URL str, given a `logId` and the `basePath` of the API endpoint
function getRequestURL(logId, basePath) {
	return `/${basePath}/${logId}?sort=${sortOpts}&filter=${startDatetimeOpt},${endDatetimeOpt}`
}
