const express = require('express');
const net = require('net');
const path = require('path');
const fs = require('fs');
const app = express();
const port = 3000;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.json());

app.get('/', (req, res) => {
    const config = loadConfig();
    res.render('index', { config, engines: [] });
});

app.use(express.static(path.join(__dirname, 'public')));


const configPath = './config.json';

function loadConfig() {
    if (fs.existsSync(configPath)) {
        const data = JSON.parse(fs.readFileSync(configPath));
        // Migrate old single controller format
        if (data.ip) {
            data.controllers = [{ id: generateId(), ip: data.ip, name: '', engines: [] }];
            delete data.ip;
            saveConfig(data);
        }
        if (!data.controllers) data.controllers = [];
        if (!data.layoutId) data.layoutId = generateLayoutId();
        if (!('layoutName' in data)) data.layoutName = '';
        data.controllers.forEach(c => {
            if (!c.engines) c.engines = [];
            if (!('name' in c)) c.name = '';
        });
        return data;
    }
    const config = { controllers: [], layoutId: generateLayoutId(), layoutName: '' };
    saveConfig(config);
    return config;
}

function saveConfig(data) {
    fs.writeFileSync(configPath, JSON.stringify(data, null, 2));
}

function generateLayoutId() {
    return 'layout-' + Math.random().toString(36).substring(2, 10);
}

function generateId() {
    return Math.random().toString(36).substring(2, 10);
}

// Accepts a string or array of commands
function sendCommand(ip, commands, callback) {
    const PORT = 2560;
    const client = new net.Socket();
    let data = '';

    const commandList = Array.isArray(commands) ? commands : [commands];

    client.connect(PORT, ip, () => {
        console.log('Connected to device at ' + ip);
        commandList.forEach(cmd => {
            console.log('Sending:', cmd);
            client.write(cmd + '\n');
        });
        client.end();
    });

    client.on('data', (chunk) => {
        data += chunk.toString();
    });

    client.on('end', () => {
        if (callback) callback(null, data);
    });

    client.on('error', (err) => {
        if (callback) callback(err, null);
    });
}

// ENGINE SCAN: Loop over cabs and find active locos
app.get('/scan-engines', async (req, res) => {
    const PORT = 2560;
    const ip = req.query.ip;
    if (!ip) return res.status(400).send('Missing ip');
    const client = new net.Socket();
    const activeCabs = [];
    let buffer = '';

    const minCab = 1;
    const maxCab = 127;
    const timeoutMs = 100;

    const connect = () => new Promise((resolve, reject) => {
        client.connect(PORT, ip, resolve);
        client.on('error', reject);
    });

    const sendCabCommand = (cab) => {
        return new Promise((resolve) => {
            buffer = '';
            const command = `<s ${cab} 1 128 0>\n`;
            client.write(command);

            const timeout = setTimeout(() => {
                resolve(false);
                client.removeListener('data', onData);
            }, timeoutMs);

            const onData = (chunk) => {
                buffer += chunk.toString();
                const match = buffer.match(new RegExp(`<l ${cab} \\d+ \\d+ \\d+>`));
                if (match) {
                    clearTimeout(timeout);
                    client.removeListener('data', onData);
                    resolve(true);
                }
            };

            client.on('data', onData);
        });
    };

    try {
        await connect();
        for (let cab = minCab; cab <= maxCab; cab++) {
            const found = await sendCabCommand(cab);
            if (found) activeCabs.push(cab);
        }
        client.end();
        res.json({ engines: activeCabs });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// Command sender
app.post('/send', (req, res) => {
    const { cmd, ip } = req.body;
    if (!cmd || !ip) return res.status(400).send('Missing command or ip');
    sendCommand(ip, cmd, (err) => {
        if (err) return res.status(500).send('Command error');
        res.sendStatus(200);
    });
});

// Setup sequence
app.post('/send/setup', (req, res) => {
    const { ip } = req.body;
    const cmds = ['<1>', '<1 MAIN>', '<1 PROG>', '<1 JOIN>'];
    if (!ip) return res.status(400).send('Missing ip');
    sendCommand(ip, cmds, (err) => {
        if (err) return res.status(500).send('Setup error');
        res.sendStatus(200);
    });
});

// Emergency stop
app.post('/send/emergency', (req, res) => {
    const { ip } = req.body;
    if (!ip) return res.status(400).send('Missing ip');
    sendCommand(ip, '<!>', (err) => {
        if (err) return res.status(500).send('Emergency stop failed');
        res.sendStatus(200);
    });
});

// Add a new controller
app.post('/add-controller', (req, res) => {
    const { ip, name = '' } = req.body;
    if (!ip) return res.status(400).send('Missing ip');
    const config = loadConfig();
    if (config.controllers.some(c => c.ip === ip)) {
        return res.status(400).send('Controller already exists');
    }
    const id = generateId();
    config.controllers.push({ id, ip, name, engines: [] });
    saveConfig(config);
    res.json({ id });
});

// Update controller IP
app.post('/set-ip', (req, res) => {
    const { id, ip } = req.body;
    const config = loadConfig();
    const ctrl = config.controllers.find(c => c.id === id);
    if (!ctrl) return res.status(404).send('Controller not found');
    ctrl.ip = ip;
    saveConfig(config);
    res.sendStatus(200);
});

app.post('/set-controller-name', (req, res) => {
    const { id, name = '' } = req.body;
    const config = loadConfig();
    const ctrl = config.controllers.find(c => c.id === id);
    if (!ctrl) return res.status(404).send('Controller not found');
    ctrl.name = name;
    saveConfig(config);
    res.sendStatus(200);
});

app.post('/set-layout-name', (req, res) => {
    const { name = '' } = req.body;
    const config = loadConfig();
    config.layoutName = name.trim();
    saveConfig(config);
    res.sendStatus(200);
});

// Delete controller
app.post('/delete-controller', (req, res) => {
    const { id } = req.body;
    const config = loadConfig();
    config.controllers = config.controllers.filter(c => c.id !== id);
    saveConfig(config);
    res.sendStatus(200);
});

app.post('/add-engine', (req, res) => {
    const { controllerId, engineId, name = '' } = req.body;
    if (!controllerId || !engineId) return res.status(400).send('Missing data');
    const config = loadConfig();
    const ctrl = config.controllers.find(c => c.id === controllerId);
    if (!ctrl) return res.status(404).send('Controller not found');
    if (ctrl.engines.some(e => e.id.toString() === engineId.toString())) {
        return res.status(400).send('Engine already exists');
    }
    ctrl.engines.push({ id: engineId.toString(), name });
    saveConfig(config);
    res.sendStatus(200);
});

app.post('/update-engine', (req, res) => {
    const { controllerId, engineId, name = '', newId } = req.body;
    const config = loadConfig();
    const ctrl = config.controllers.find(c => c.id === controllerId);
    if (!ctrl) return res.status(404).send('Controller not found');
    const eng = ctrl.engines.find(e => e.id.toString() === engineId.toString());
    if (!eng) return res.status(404).send('Engine not found');
    const targetId = (newId || engineId).toString();
    if (targetId !== engineId.toString() && ctrl.engines.some(e => e.id.toString() === targetId)) {
        return res.status(400).send('Engine already exists');
    }
    eng.id = targetId;
    eng.name = name;
    saveConfig(config);
    res.sendStatus(200);
});

app.post('/delete-engine', (req, res) => {
    const { controllerId, engineId } = req.body;
    const config = loadConfig();
    const ctrl = config.controllers.find(c => c.id === controllerId);
    if (!ctrl) return res.status(404).send('Controller not found');
    ctrl.engines = ctrl.engines.filter(e => e.id.toString() !== engineId.toString());
    saveConfig(config);
    res.sendStatus(200);
});

// Get config
app.get('/get-config', (req, res) => {
    const config = loadConfig();
    res.json(config);
});

if (require.main === module) {
    app.listen(port, () => {
        console.log(`DCC Web App running at http://localhost:${port}`);
    });
}

module.exports = app;
