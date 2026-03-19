
let temperature = null;
let socket = null;

function initSocketIO() {
    socket = io(`http://${window.location.host}`);

    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });

    socket.on('temp', (data) => {
        console.log('Received temperature:', data);
        temperature = data; 
        updateTemperatureDisplay();
    });

    socket.on('error', (error) => {
        console.error('Socket error:', error);
    });
}

function updateTemperatureDisplay() {
    const tempElement = document.getElementById('temp');

    if (tempElement != temperature ) {
        tempElement.textContent = temperature.toFixed(2);
    }
}

window.addEventListener("load", initSocketIO);
