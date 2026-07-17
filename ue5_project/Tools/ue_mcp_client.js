const fs = require('fs');
const http = require('http');

const args = process.argv.slice(2);
const command = args[0] || 'list';
const portIndex = args.indexOf('--port');
const port = portIndex >= 0 ? Number(args[portIndex + 1]) : Number(process.env.UE_MCP_PORT || 8181);
let sessionId = null;

function parseSse(body) {
  try {
    return JSON.parse(body);
  } catch (_) {
    // Streamable HTTP may return SSE instead of a single JSON document.
  }
  for (const rawLine of body.split(/\r?\n/)) {
    const line = rawLine.trim();
    const jsonText = line.startsWith('data:') ? line.slice(5).trim() : line;
    if (!jsonText.startsWith('{')) continue;
    try {
      return JSON.parse(jsonText);
    } catch (_) {
      // Keep looking for the next SSE data line.
    }
  }
  throw new Error(`No JSON response: ${body.slice(0, 500)}`);
}

function request(method, params = {}) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method, params });
    const headers = {
      Accept: 'application/json, text/event-stream',
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(payload),
    };
    if (sessionId) headers['Mcp-Session-Id'] = sessionId;

    const req = http.request(
      { hostname: '127.0.0.1', port, path: '/mcp', method: 'POST', headers, timeout: 600000 },
      (res) => {
        if (res.headers['mcp-session-id']) sessionId = res.headers['mcp-session-id'];
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          try {
            const parsed = parseSse(body);
            if (parsed.error) reject(new Error(JSON.stringify(parsed.error)));
            else resolve(parsed);
          } catch (error) {
            reject(error);
          }
        });
      },
    );
    req.on('timeout', () => req.destroy(new Error('MCP request timed out')));
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

async function initialize() {
  return request('initialize', {
    protocolVersion: '2025-11-25',
    capabilities: {},
    clientInfo: { name: 'aociety-codex-builder', version: '1.0.0' },
  });
}

async function tool(name, argumentsObject = {}) {
  return request('tools/call', { name, arguments: argumentsObject });
}

async function callToolset(toolsetName, toolName, argumentsObject = {}) {
  return tool('call_tool', {
    toolset_name: toolsetName,
    tool_name: toolName,
    arguments: argumentsObject,
  });
}

function firstText(result) {
  const content = result?.result?.content || result?.content || [];
  return content.find((item) => item.type === 'text')?.text || '';
}

async function main() {
  await initialize();

  if (command === 'list') {
    const result = await tool('list_toolsets');
    process.stdout.write(firstText(result) || JSON.stringify(result, null, 2));
    return;
  }

  if (command === 'describe') {
    const name = args[1];
    if (!name) throw new Error('Usage: describe <toolset> [--port N]');
    const result = await tool('describe_toolset', { toolset_name: name });
    process.stdout.write(firstText(result) || JSON.stringify(result, null, 2));
    return;
  }

  if (command === 'exec-file') {
    const filePath = args[1];
    if (!filePath) throw new Error('Usage: exec-file <absolute-python-file> [--port N]');
    const normalized = filePath.replace(/\\/g, '/').replace(/'/g, "\\'");
    const script = [
      'import runpy',
      `runpy.run_path(r'${normalized}', run_name='__main__')`,
    ].join('\n');
    const result = await callToolset(
      'editor_toolset.toolsets.programmatic.ProgrammaticToolset',
      'execute_tool_script',
      { script },
    );
    process.stdout.write(firstText(result) || JSON.stringify(result, null, 2));
    return;
  }

  if (command === 'call') {
    const toolsetName = args[1];
    const toolName = args[2];
    const jsonArgs = args[3] ? JSON.parse(args[3]) : {};
    if (!toolsetName || !toolName) {
      throw new Error('Usage: call <toolset> <tool> [json-arguments] [--port N]');
    }
    const result = await callToolset(toolsetName, toolName, jsonArgs);
    process.stdout.write(firstText(result) || JSON.stringify(result, null, 2));
    return;
  }

  if (command === 'capture-viewport') {
    const outputPath = args[1] || 'E:/Aociety-NEW/ue5_project/Saved/AocietyCaptures/viewport.png';
    const annotate = args.includes('--annotate');
    const cameraResult = await callToolset(
      'EditorToolset.EditorAppToolset',
      'GetCameraTransform',
      {},
    );
    const camera = JSON.parse(firstText(cameraResult)).returnValue;
    const result = await callToolset(
      'EditorToolset.EditorAppToolset',
      'CaptureViewport',
      {
        captureTransform: camera,
        annotations: {
          gridSpacing: annotate ? 500 : 0,
          gridExtent: annotate ? 10000 : 0,
          gridHeight: 0,
          maxLabelDistance: annotate ? 20000 : 0,
          classFilter: { refPath: '/Script/Engine.Actor' },
          maxLabels: annotate ? 40 : 0,
        },
        bShowUI: false,
      },
    );
    const text = firstText(result);
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (_) {
      throw new Error(text || JSON.stringify(result));
    }
    const capture = parsed.returnValue;
    if (!capture?.image?.data) throw new Error(`Capture returned no image data: ${text.slice(0, 500)}`);
    fs.writeFileSync(outputPath, Buffer.from(capture.image.data, 'base64'));
    process.stdout.write(JSON.stringify({
      outputPath,
      cameraLocation: capture.cameraLocation,
      cameraRotation: capture.cameraRotation,
      cameraFOV: capture.cameraFOV,
      labeledActors: capture.labeledActors,
    }, null, 2));
    return;
  }

  if (command === 'capture') {
    const outputPath = args[1] || 'E:/Aociety-NEW/ue5_project/Saved/AocietyCaptures/editor.png';
    const result = await callToolset(
      'EditorToolset.EditorAppToolset',
      'CaptureEditorImage',
      { width: 1920, height: 1080, path: '' },
    );
    const text = firstText(result);
    const parsed = JSON.parse(text);
    const data = parsed.returnValue?.data;
    if (!data) throw new Error(`Capture returned no image data: ${text.slice(0, 500)}`);
    fs.writeFileSync(outputPath, Buffer.from(data, 'base64'));
    process.stdout.write(outputPath);
    return;
  }

  throw new Error(`Unknown command: ${command}`);
}

module.exports = {
  initialize,
  tool,
  callToolset,
  firstText,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}
