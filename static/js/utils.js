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

function getRequestURL(logId, basePath) {
	return `/${basePath}/${logId}?sort=${sortOpts}&filter=${startDatetimeOpt},${endDatetimeOpt}`;
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
	if (startDatetime < minDatetimeOpt) {
		window.alert(`Start date time is less than minimum value in log file (${minDatetimeOpt})!`);
		return false;
	}
	if (endDatetime > maxDatetimeOpt) {
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

function getDatetimeBoundsFromData(data) {
	// convert into formatted timestampts YYYY-mm-DD HH:MM:SS
	const fmtdTimestamps = data.map(row => row[1]).map(tstmp => {
		const [_, mo, dt, time, yr] = tstmp.split(' ');

		// define month map
		const month_map = {
			"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
			"Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
		};
		const month = month_map[mo];

		return `${yr}-${month}-${dt} ${time}`;
	});

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

	// set defaults
	startDateEl.value = start.split(' ')[0];
	startTimeEl.value = start.split(' ')[1];

	endDateEl.value = end.split(' ')[0];
	endTimeEl.value = end.split(' ')[1];
}

function resetFilterOpts() {
	startDatetimeOpt = "";
	endDatetimeOpt = "";
}

export {
	getRequestURL,
	parseDatetimeInputs,
	validateFilterDates,
	setFilterOpts,
	getFilterOpts,
	setSortOpts,
	getSortOpts,
	resetSortOpts,
	resetFilterOpts,
	setFilterRange,
	getDatetimeBoundsFromData,
};
