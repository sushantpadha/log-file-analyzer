import {
	parseDatetimeInputs,
	validateFilterDates,
	setFilterOpts,
	resetFilterOpts,
	getPlotRequest,
	getPlotStatusRequestURL,
	getPlotURL,
	getMetadataRequestURL,
	setFilterRange,
	fmtTimestamp,
	updateFilterValues,
	resetFilterValues,
} from "./utils.js";

const selectEl = document.getElementById('log-select-plot');
const optionsDiv = document.getElementById('plot-options');

const plotDisplayContainer = document.getElementById('plot-display-container'); // parent el
const loadingMessage = document.getElementById('plot-loading-message');
const errorMessage = document.getElementById('plot-error-message');
const plotDisplayArea = document.getElementById('plot-display-area'); // only plots displayed here

const genPlotsBtn = document.getElementById('generate-plots-btn');
// returns NodeList of all plot options elements
const plotTypeCheckboxes = document.querySelectorAll('input[name="plot_type"]');

const filterApplyBtn = document.getElementById('filter-apply-btn');
const filterResetBtn = document.getElementById('filter-reset-btn');

let oldSelectedId = selectEl.value;

// ================= add event listeners ============================

document.addEventListener('DOMContentLoaded', updateOptionsDiv);
selectEl.addEventListener('click', () => {
	updateOptionsDiv();
	if (selectEl.value && selectEl.value !== oldSelectedId) {
		oldSelectedId = selectEl.value;
		resetFilterValues();
		updateFilterOptsValues();
	}
});

filterApplyBtn.addEventListener('click', filterBtnCallback);

filterResetBtn.addEventListener('click', () => {
	updateFilterOptsValues();
	updateFilterValues(true);
});

genPlotsBtn.addEventListener('click', generatePlots);

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
}

// toggle displaying of options div, reset value and set limits for filter inputs
function updateOptionsDiv() {
	const selectedLogId = selectEl.value;
	if (selectedLogId) {
		optionsDiv.style.display = 'flex';
	}
	else {
		optionsDiv.style.display = 'none';
		return;
	}

	updateFilterOptsValues();
}

// send request for plot generation, query status and populate plots div with response
function generatePlots() {
	// parse plot options

	// filter checked > extract values (as array)
	const plotOpts = Array.from(plotTypeCheckboxes)
		.filter(node => node.checked)
		.map(node => node.value)

	// TODO: inc filtering opts

	const selectedLogId = selectEl.value;

	// clear previous content
	plotDisplayArea.innerHTML = '';
	plotDisplayArea.style.display = 'none';
	loadingMessage.style.display = 'none';
	errorMessage.style.display = 'none';

	// if invalid log id is passed
	if (!selectedLogId) {
		return;
	}

	const { endpoint, payload } = getPlotRequest(selectedLogId, plotOpts);

	console.log(`Sending @ ${endpoint} payload: ${payload.body}`)

	// make request to generate plots
	fetch(endpoint, payload)
		.then(response => {
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			return response.json();
		})
		.then(result => {
			// error handling
			if (result.error) {
				errorMessage.textContent = `Error loading data: ${result.error}`;
				errorMessage.style.display = 'block';
				return;
			}

			// display loading message
			loadingMessage.style.display = 'block';

			// receive response for status file which will be queried for job status and plot filenames
			// const statusPath = result.status_file;

			// set max attempts as 60 (60 * 500ms = 30s)
			let attempts = 0;
			const maxAttempts = 60;

			// query every 500 ms
			const interval = setInterval(() => {
				attempts++;

				// request for url
				fetch(getPlotStatusRequestURL())
					.then(response => {
						if (!response.ok) {
							throw new Error(`Error requesting job status file! status: ${response.status}`);
						}
						return response.json();
					})
					.then(result => {
						// error handling
						if (result.error) {
							errorMessage.textContent = `Error in plot generation / status file I/O: ${result.error}`;
							errorMessage.style.display = 'block';
							return;
						}

						// if done processing
						if (result.status == 'done') {
							// stop looping
							clearInterval(interval);

							// remove loading msg
							loadingMessage.style.display = 'none';

							// populate plots div
							Object.entries(result.plot_files).forEach(([type, file]) => {

								const plotDiv = document.createElement('div');
								plotDiv.classList.add('plot-container');

								const plotImg = document.createElement('img');
								plotImg.classList.add('plot-image');
								// simply set src to point to plot file path
								plotImg.src = getPlotURL(file);

								const plotDLLink = document.createElement('a');
								plotDLLink.classList.add('plot-dl-link');
								plotDLLink.textContent = "Download Plot";

								plotDLLink.href = getPlotURL(file, true);
								plotDLLink.download = file

								plotDiv.appendChild(plotImg);
								plotDiv.appendChild(plotDLLink);

								plotDisplayArea.appendChild(plotDiv);
							});

							// hide loading area
							loadingMessage.style.display = 'none';

							// show plots
							plotDisplayArea.style.display = 'flex';

						}
					})

				if (attempts >= maxAttempts) {
					clearInterval(interval);
					// ! raise error after timeout
					loadingMessage.style.display = 'none';
					errorMessage.textContent = `Error requesting job status file! Request timed out.`;
					errorMessage.style.display = 'block';
					console.error(`Error requesting job status file! Request timed out.`);
				}
			}, 500)
		})
		.catch(error => {
			loadingMessage.style.display = 'none';
			errorMessage.textContent = `Error generating plots / fetching status: ${error}`;
			errorMessage.style.display = 'block';
			console.error('Error generating plots / fetching status:', error);
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
