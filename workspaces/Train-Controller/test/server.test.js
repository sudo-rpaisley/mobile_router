const request = require('supertest');
const fs = require('fs');
const app = require('../server');
const assert = require('assert');

let originalConfig;

before(() => {
  originalConfig = fs.readFileSync('config.json', 'utf8');
});

after(() => {
  fs.writeFileSync('config.json', originalConfig);
});

describe('API endpoints', function() {
  this.timeout(5000);

  it('sets the layout name', async () => {
    await request(app)
      .post('/set-layout-name')
      .send({ name: 'Test Layout' })
      .expect(200);
    const config = JSON.parse(fs.readFileSync('config.json'));
    assert.strictEqual(config.layoutName, 'Test Layout');
  });

  it('adds controller and manages engines', async () => {
    const addRes = await request(app)
      .post('/add-controller')
      .send({ ip: '10.0.0.1', name: 'Ctrl' })
      .expect(200);
    const ctrlId = addRes.body.id;
    let config = JSON.parse(fs.readFileSync('config.json'));
    let ctrl = config.controllers.find(c => c.id === ctrlId);
    assert(ctrl, 'controller should exist');

    await request(app)
      .post('/add-engine')
      .send({ controllerId: ctrlId, engineId: '3', name: 'E3' })
      .expect(200);
    config = JSON.parse(fs.readFileSync('config.json'));
    let eng = config.controllers.find(c => c.id === ctrlId).engines.find(e => e.id === '3');
    assert(eng, 'engine should be added');

    await request(app)
      .post('/update-engine')
      .send({ controllerId: ctrlId, engineId: '3', name: 'E4', newId: '4' })
      .expect(200);
    config = JSON.parse(fs.readFileSync('config.json'));
    eng = config.controllers.find(c => c.id === ctrlId).engines.find(e => e.id === '4');
    assert(eng && eng.name === 'E4', 'engine should be updated');

    await request(app)
      .post('/delete-controller')
      .send({ id: ctrlId })
      .expect(200);
    config = JSON.parse(fs.readFileSync('config.json'));
    ctrl = config.controllers.find(c => c.id === ctrlId);
    assert(!ctrl, 'controller should be deleted');
  });
});
