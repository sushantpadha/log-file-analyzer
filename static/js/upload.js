const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const fileStatusArea = document.getElementById('file-status-area');

// ====================== event listeners =======================

// Ref: https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API

// prevent default behvaiour
dropArea.addEventListener('dragover', (e) => {
	e.preventDefault();
	dropArea.classList.add('dragover');
});

dropArea.addEventListener('dragleave', (e) => {
	e.preventDefault();
	dropArea.classList.remove('dragover');
});

dropArea.addEventListener('drop', (e) => {
	e.preventDefault();
	dropArea.classList.remove('dragover');
	// get the files from the drop event and handle them
	// Ref: https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer
	const files = e.dataTransfer.files;
	if (files.length) {
		handleFiles(files);
	}
});

// make whole drop area clickable
dropArea.addEventListener('click', () => {
	fileInput.click();
});

fileInput.addEventListener('change', () => {
	if (fileInput.files.length) {
		handleFiles(fileInput.files);
		// reset input to allow uploading the same file again if needed
		fileInput.value = '';
	}
});

// ================ handle files ====================

function handleFiles(files) {
	Array.from(files).forEach(file => {
		// no additional checks (server will handle it)
		uploadFile(file);
	});
}

// =============== upload and process files ===============

async function uploadFile(file) {

	// Ref: https://developer.mozilla.org/en-US/docs/Web/API/FormData
	// create formdata object and make `fetch` request

	const formData = new FormData();
	formData.append('log_file', file);

	// add a temporary "processing" tile
	const tempId = `tile-${Date.now()}-${Math.random().toString(16).slice(2)}`;
	addStatusTile(file.name, null, 'Processing...', tempId);

	// Ref: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch

	try {
		const response = await fetch('/upload', {
			method: 'POST',
			body: formData
		});
		const result = await response.json();
		console.log('Server response:', result);
		// update the specific tile with the result
		updateStatusTile(tempId, file.name, result.success, result.message);
	}
	catch (err) {
		console.error('Upload error:', err);
		// update the specific tile with the error
		updateStatusTile(tempId, file.name, false, `Upload failed: ${err.message}`);
	}
}

// =================== helper funcs for making status tiles ===================

// create a status tile with filename, success value, message to be displayed and an id to uniquely identify
function addStatusTile(filename, success, message, tileId) {
	const tile = document.createElement('div');
	tile.classList.add('file-tile');
	tile.id = tileId;

	const statusIndicator = document.createElement('span');
	const nameSpan = document.createElement('span');
	nameSpan.textContent = filename;
	const messageSpan = document.createElement('span');
	messageSpan.classList.add('status-message');
	messageSpan.textContent = message;

	// status is either success (true), error (false) or processing (otherwise)

	if (success === true) {
		tile.classList.add('success');
	} else if (success === false) {
		tile.classList.add('error');
	} else {
		// create and add loading emoji
		const loading = document.createElement('div');
		loading.classList.add('loading');
		loading.innerText = '⏳';
		statusIndicator.appendChild(loading);
	}

	// add elements in order
	tile.appendChild(statusIndicator);
	tile.appendChild(nameSpan);
	tile.appendChild(messageSpan);

	// prepend new tiles so latest uploads are at the top
	fileStatusArea.insertBefore(tile, fileStatusArea.firstChild);
}

// update status tile with ...
function updateStatusTile(tileId, filename, success, message) {
	const tile = document.getElementById(tileId);

	// exit if tile not found
	if (!tile) return;

	// clear existing content and classes first
	tile.innerHTML = '';
	tile.classList.remove('success', 'error');

	const statusIndicator = document.createElement('span');
	const nameSpan = document.createElement('span');
	nameSpan.textContent = filename;
	const messageSpan = document.createElement('span');
	messageSpan.classList.add('status-message');
	messageSpan.textContent = message;


	// status is either success (true), or, error (false) now
	// this time add indicators

	if (success === true) {
		tile.classList.add('success');
		statusIndicator.textContent = '✅ '; // Simple indicator
	} else if (success === false) {
		tile.classList.add('error');
		statusIndicator.textContent = '❌ '; // Simple indicator
	}

	tile.appendChild(statusIndicator);
	tile.appendChild(nameSpan);
	tile.appendChild(messageSpan);
}