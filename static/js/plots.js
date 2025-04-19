const selectEl = document.getElementById('log-select-plot');
const optionsDiv = document.getElementById('plot-options');

const plotDisplayContainer = document.getElementById('plots-display-container'); // parent el
const loadingMessage = document.getElementById('plot-loading-message');
const errorMessage = document.getElementById('plot-error-message');
const plotDisplayArea = document.getElementById('plots-display-area'); // only plots displayed here

const genPlotsBtn = document.getElementById('generate-plots-btn');
// returns NodeList of all plot options elements
const plotTypeCheckboxes = document.querySelectorAll('input[name="plot_type"]');

// add listener for `selectEl` to `updateOptionsDiv`

// add (HTML and) listener for submit button on filter input controls

// add listener to `generatePlots` for constructing and sending API request and call `displayPlots`

// change the `plotDisplayArea` to show processing

// when `displayPlots` receives response, update `plotDisplayArea` to display desired plots and update download buttons

selectEl.addEventListener('click', updateOptionsDiv);

genPlotsBtn.addEventListener('click', generatePlots);

function updateOptionsDiv() {
	if (selectEl.value) {
		optionsDiv.style.display = 'block';
	}
	else {
		optionsDiv.style.display = 'none';
	}
}

// TODO: filtering

function generatePlots() {
	// parse plot options

	// filter checked > extract values > join as ,-separated str
	const plotOpts = Array.from(plotTypeCheckboxes)
		.filter(node => node.checked)
		.map(node => node.value).join(',');

	// TODO: inc filtering opts

	const selectedLogId = selectEl.value;

	// clear previous content
	plotDisplayArea.innerHTML = '';
	plotDisplayArea.style.display = 'none';
	loadingMessage.style.display = 'none';
	errorMessage.style.display = 'none';

	if (!selectedLogId) {
		// TODO: error
	}

	const reqURL = getRequestURL(selectedLogId, 'generate_plots');

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
			if (result.error) {
				errorMessage.textContent = `Error loading data: ${result.error}`;
				errorMessage.style.display = 'block';
				return;
			}

			// display loading message
			loadingMessage.style.display = 'block';

			// receive response for plot filenames, that will be sent in subsequent request
			
		});

}






// returns the full request URL str, given a `logId` and the `basePath` of the API endpoint
function getRequestURL(logId, basePath) {
	return `/${basePath}/${logId}?sort=${sortOpts}&filter=${startDatetimeOpt},${endDatetimeOpt}`
}