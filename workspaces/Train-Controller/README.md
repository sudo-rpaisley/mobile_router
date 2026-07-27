# Train Controller

Train Controller is a small web interface for sending Digital Command Control (DCC) commands to your model railway.
It is built with Node.js and Express and communicates with the train controller device over TCP.

## Features

- Control DCC engines from any modern browser
- Scan for active engines on the network
- Save the controller IP address and layout ID
- Emergency stop button for quick shutdown
- Prevent adding duplicate engine IDs to a controller
- Prevent adding the same controller more than once
- Ensure engine commands target only their assigned controller
- Dark mode toggle with a rounded switch showing sun and moon icons
- Toast notifications for errors and status messages
- Inline IP editing for controllers with a simple save button
- IP address field appears as plain text until editing
- Inline engine name editing using the same pencil icon
- Sleeker controller and engine management layout
- Collapse controller cards to hide engine controls
- Speed sliders show tick marks and a digital readout of the current value
- Min, center and max speed labels displayed above each slider
- Engine addresses shown below the name instead of in the title
- Controllers can be named and names are displayed above the IP
- Engine lists and names are saved in `config.json`
- Stopping an engine also resets its speed slider to the middle

## Setup

1. Install dependencies
   ```bash
   npm install
   ```
2. Start the application
   ```bash
   node server.js
   ```
3. Browse to [http://localhost:3000](http://localhost:3000) and configure the controller IP.

Configuration is stored in `config.json`. The file is created automatically the first time you run the server.

