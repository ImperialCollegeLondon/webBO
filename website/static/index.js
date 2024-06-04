function deleteDataset(noteId) {
    fetch('/delete-dataset', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        window.location.href = "/";
    });
}

function deleteExperiment(noteId) {
    fetch('/delete-experiment', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

function addSampleDataset() {
    fetch('/add-sample-dataset', { method: 'POST' }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

function addParameterElement(noteId) {
    fetch('/add-parameter-element', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

