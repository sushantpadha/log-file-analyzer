const sortResetBtn = document.getElementById('sort-reset-btn');
const filterApplyBtn = document.getElementById('filter-apply-btn');
const filterResetBtn = document.getElementById('filter-reset-btn');

const startDateEl = document.getElementById('start-date');
const startTimeEl = document.getElementById('start-time');
const endDateEl = document.getElementById('end-date');
const endTimeEl = document.getElementById('end-time');

// NOTE: endpoint paths are only defined / hardcoded here (?)

// global variables for setting parameters for fetch request
let sortOpts = "";
let startDatetimeOpt = ""
let endDatetimeOpt = ""

// these are set from unfiltered csv and used for validating filter options
let minDatetimeOpt = startDatetimeOpt;
let maxDatetimeOpt = endDatetimeOpt;

function getCSVRequestURL(logId, forDownload = false) {
	const endpoint = (forDownload ? '/download_csv/' : '/get_csv/')

	return endpoint + `${logId}?sort=${sortOpts}&filter=${startDatetimeOpt},${endDatetimeOpt}`;
}

function getMetadataRequestURL(logId) {
	return `/get_metadata/${logId}`;
}

function getPlotRequest(logId, plotOpts, customCode) {
	const endpoint = "/generate_plots/";

	const payload = {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			log_id: logId,
			plot_options: plotOpts,
			// sending filter options as formatted string
			// for uniformity in backend code
			filter_options: `${startDatetimeOpt},${endDatetimeOpt}`,
			custom_code: customCode,
		})
	};
	return { endpoint, payload };
}

function getPlotStatusRequestURL() {
	return '/status'
}

function getPlotURL(plotFile, forDownload = false) {
	const endpoint = (forDownload ? '/download_plot/' : '/get_plot/')
	// add a query parameter to URL to prevent displaying cache
	return endpoint + `${plotFile}?ts=${Date.now()}`;
}

function parseDatetimeInputs() {
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

	return { startDatetime, endDatetime };
}

function validateFilterDates(startDatetime, endDatetime) {
	// YYYY-mm-DD HH:MM:SS is already in valid lexico order !!!
	if (minDatetimeOpt && startDatetime < minDatetimeOpt) {
		window.alert(`Start date time is less than minimum value in log file (${minDatetimeOpt})!`);
		return false;
	}
	if (maxDatetimeOpt & endDatetime > maxDatetimeOpt) {
		window.alert(`End date time is more than maximum value in log file (${maxDatetimeOpt})!`);
		return false;
	}
	// basic check
	if (startDatetime > endDatetime) {
		window.alert('Start date time is more than end date time!');
		return false;
	}
	return true;
}

function setFilterOpts(startDatetime, endDatetime) {
	startDatetimeOpt = startDatetime;
	endDatetimeOpt = endDatetime;
}

function getFilterOpts() {
	return { startDatetimeOpt, endDatetimeOpt };
}

function fmtTimestamp(csvTimestamp) {
	const [_, mo, dt, time, yr] = csvTimestamp.split(' ');

	// define month map
	const month_map = {
		"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
		"Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
	};
	const month = month_map[mo];

	return `${yr}-${month}-${dt} ${time}`;
}

function getDatetimeBoundsFromData(data) {
	// convert into formatted timestampts YYYY-mm-DD HH:MM:SS
	const fmtdTimestamps = data.map(row => row[1]).map(fmtTimestamp);

	// use lexi ordering with `reduce` to get min and max
	const start = fmtdTimestamps.reduce((minm, curr) => (curr < minm ? curr : minm));
	const end = fmtdTimestamps.reduce((maxm, curr) => (curr > maxm ? curr : maxm));

	return { start, end };
}

function getSortOpts() {
	return sortOpts.split(',');
}

function setSortOpts(opt) {
	const field = Number(opt.charAt(1));
	// remove prev occurence of any options for this field
	const opts = sortOpts && sortOpts !== ''
		? sortOpts.split(',').filter(o => Number(o.charAt(1)) !== field)
		: [];
	sortOpts = [opt, ...opts].join(',');
}

function resetSortOpts() {
	sortOpts = "";
}

function setFilterRange(start, end) {
	minDatetimeOpt = start;
	maxDatetimeOpt = end;

	// set limits for input elemets
	startDateEl.min = start.split(' ')[0];
	startDateEl.max = end.split(' ')[0];
	startTimeEl.min = start.split(' ')[1];
	startTimeEl.max = end.split(' ')[1];

	endDateEl.min = start.split(' ')[0];
	endDateEl.max = end.split(' ')[0];
	endTimeEl.min = start.split(' ')[1];
	endTimeEl.max = end.split(' ')[1];
}

function updateFilterValues(force = false) {
	console.log(`resetting filter values [${force}] ${startDatetimeOpt} ${endDatetimeOpt}`);
	// set values to defaults
	startDateEl.value = (force || !startDateEl.value) ? startDatetimeOpt.split(' ')[0] : startDateEl.value;
	startTimeEl.value = (force || !startTimeEl.value) ? startDatetimeOpt.split(' ')[1] : startTimeEl.value;

	endDateEl.value = (force || !endDateEl.value) ? endDatetimeOpt.split(' ')[0] : endDateEl.value;
	endTimeEl.value = (force || !endTimeEl.value) ? endDatetimeOpt.split(' ')[1] : endTimeEl.value;
}

function resetFilterOpts() {
	startDatetimeOpt = "";
	endDatetimeOpt = "";
}

function resetFilterValues() {
	startDateEl.value = "";
	startTimeEl.value = "";

	endDateEl.value = "";
	endTimeEl.value = "";
}

export {
	getCSVRequestURL,
	getMetadataRequestURL,
	getPlotRequest,
	getPlotStatusRequestURL,
	getPlotURL,
	parseDatetimeInputs,
	validateFilterDates,
	setFilterOpts,
	getFilterOpts,
	setSortOpts,
	getSortOpts,
	resetSortOpts,
	resetFilterOpts,
	fmtTimestamp,
	setFilterRange,
	updateFilterValues,
	resetFilterValues,
	getDatetimeBoundsFromData,
};
