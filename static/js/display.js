const selectElement = document.getElementById('log-select');
const displayArea = document.getElementById('log-display-area');
const logTable = document.getElementById('log-table');
const loadingMessage = document.getElementById('loading-message');
const errorMessage = document.getElementById('error-message');
const controlsDiv = document.getElementById('controls');
const downloadLink = document.getElementById('download-csv-link');
const sortResetBtn = document.getElementById('sort-reset-btn')

let sort_opts = "";

// some peculiarity of the `this` keyword in arrow functions / regular functions
document.addEventListener('DOMContentLoaded', function () { updateTable(selectElement); })
selectElement.addEventListener('change', function () { updateTable(this); });
selectElement.addEventListener('click', function () { updateTable(this); });

sortResetBtn.addEventListener('click', () => {
	sort_opts = "";
	updateTable(selectElement);
});

// when sort btn is clicked, updates the sort_opts global var
function sortBtnCallback(type, field, el) {
	// type = +/-
	// field is int from 0 - 4 (inc.)
	const opt = `${type}${field}`;

	// console.log(`button ${el} clicked with ${opt}`)
	// console.log(`prev opts: ${sort_opts}`)

	// remove prev occurence of any options for this field
	const opts = sort_opts && sort_opts !== ''
		? sort_opts.split(',').filter(o => Number(o.charAt(1)) !== field)
		: [];

	// console.log(`proc opts: ${opts}`)

	sort_opts = [opt, ...opts].join(',');

	// console.log(`new opts: ${sort_opts}`)

	// finally, update table
	updateTable(selectElement);
}

function updateTable(el) {
	const selectedLogId = el.value;
	// console.log(`/get_csv/${selectedLogId}?sort=${sort_opts}`);

	// clear table content and remove controls and error messages
	logTable.querySelector('thead').innerHTML = '';
	logTable.querySelector('tbody').innerHTML = '';
	errorMessage.style.display = 'none';
	controlsDiv.style.display = 'none';

	// parse sort_opts to highlight buttons
	const parsed_sort_opts = sort_opts.split(',');
	console.log(parsed_sort_opts);

	if (selectedLogId) {
		loadingMessage.style.display = 'block';
		// fetch csv data from backend
		fetch(`/get_csv/${selectedLogId}?sort=${sort_opts}`)
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

					// ▲▼ add buttons

					const btn1 = document.createElement('button');
					btn1.textContent = '▲';
					btn1.classList.add('btn-sort');
					btn1.classList.add('asc');
					if (parsed_sort_opts.includes(`+${colIdx}`))
						btn1.classList.add('active');
					btn1.addEventListener('click', (ev) => sortBtnCallback('+', colIdx, ev.currentTarget));
					th.appendChild(btn1)

					const btn2 = document.createElement('button');
					btn2.textContent = '▼';
					btn2.classList.add('btn-sort');
					btn2.classList.add('desc');
					if (parsed_sort_opts.includes(`-${colIdx}`))
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

				// show controls and set download link and filename
				controlsDiv.style.display = 'block';
				downloadLink.href = `/download_csv/${selectedLogId}`;
				downloadLink.download = `${selectedLogId}.csv`;

			})
			.catch(error => {
				loadingMessage.style.display = 'none';
				errorMessage.textContent = `Error fetching CSV data: ${error}`;
				errorMessage.style.display = 'block';
				console.error('Error fetching CSV:', error);
			});
	}
}

// document.getElementById('filter-btn').addEventListener('click', () => alert('Filter not implemented'));