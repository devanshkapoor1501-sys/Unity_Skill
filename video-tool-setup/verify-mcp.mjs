import { pathToFileURL } from 'node:url';

const sdk = 'C:/Users/Divansh Kapoor/AppData/Roaming/npm/node_modules/oh-my-codex/node_modules/@modelcontextprotocol/sdk/dist/esm';
const { Client } = await import(pathToFileURL(`${sdk}/client/index.js`).href);
const { StreamableHTTPClientTransport } = await import(pathToFileURL(`${sdk}/client/streamableHttp.js`).href);
const { StdioClientTransport } = await import(pathToFileURL(`${sdk}/client/stdio.js`).href);
const [kind, target, ...args] = process.argv.slice(2);
const client = new Client({ name: 'codex-setup-verification', version: '1.0.0' });
const transport = kind === 'remote'
  ? new StreamableHTTPClientTransport(new URL(target))
  : new StdioClientTransport({ command: target, args, stderr: 'ignore',
      ...(process.env.ELECTRON_RUN_AS_NODE ? { env: { ELECTRON_RUN_AS_NODE: process.env.ELECTRON_RUN_AS_NODE } } : {}) });
try {
  await client.connect(transport, { timeout: 30000 });
  const result = await client.listTools({}, { timeout: 30000 });
  console.log(JSON.stringify({ ok: true, kind, toolCount: result.tools.length, tools: result.tools.map(t => t.name) }));
  if (process.env.SETUP_PROBE_TOOL) {
    const probe = await client.callTool({ name: process.env.SETUP_PROBE_TOOL, arguments: {} }, undefined, { timeout: 30000 });
    console.log(JSON.stringify({ probe: process.env.SETUP_PROBE_TOOL, ok: !probe.isError,
      ...(probe.isError ? { error: probe.content?.filter(c => c.type === 'text').map(c => c.text).join('\n').slice(0, 500) } : {}) }));
    if (probe.isError) process.exitCode = 1;
  }
} catch (error) {
  console.log(JSON.stringify({ ok: false, kind, error: error.message }));
  process.exitCode = 1;
} finally {
  await client.close().catch(() => {});
}
