function deleteDataset(nodeId) {
    fetch('/delete-dataset', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

function deleteExperiment(nodeId) {
    fetch('/delete-experiment', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

function addParameterElement(nodeId) {
    fetch('/add-parameter-element', { method: 'POST', body: JSON.stringify({ noteId: noteId }) }).then((_res) => {
        WebTransportBidirectionalStream.location.href = "/";
    });
}

