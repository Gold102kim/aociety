const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Ajv2020 = require('ajv/dist/2020');
const addFormats = require('ajv-formats');

const root = path.resolve(__dirname, '..');
const schema = JSON.parse(fs.readFileSync(path.join(root, 'contracts', 'launcher-session.schema.json'), 'utf8'));
assert.ok(schema.required.includes('agent'), 'Launcher session schema must require the agent block.');

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(schema);
const session = {
  contractVersion: '1.0',
  launchId: 'd7c78763-60f6-4c62-8f66-c64c731d1b7e',
  issuedAt: '2026-07-17T00:00:00.000Z',
  expiresAt: '2026-07-17T00:02:00.000Z',
  launcher: { version: '0.3.0', platform: 'win32', locale: 'zh-CN' },
  account: { accountId: 'account-test', displayName: '测试居民' },
  agent: {
    agentId: '60f00f7a-e37e-44dc-bd35-e0d872ad6cb5',
    status: 'READY',
    profileVersion: 1,
    baseModelId: 'deepseek-v4-flash',
  },
  auth: { ticket: 'prototype_ticket', ticketType: 'prototype-local', exchangeUrl: null },
  game: { channel: 'development' },
};

assert.equal(validate(session), true, JSON.stringify(validate.errors, null, 2));
console.log('Launcher contract tests passed.');
