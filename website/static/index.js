function deleteDataset(noteId) {
    fetch(process.env.URL_PREFIX + '/delete-dataset', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

function deleteExperiment(noteId) {
    fetch(process.env.URL_PREFIX + '/delete-experiment', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

function addSampleDataset() {
    fetch(process.env.URL_PREFIX + '/add-sample-dataset', { method: 'POST' }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

function addParameterElement(noteId) {
    fetch(process.env.URL_PREFIX + '/add-parameter-element', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

