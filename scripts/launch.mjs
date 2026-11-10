import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { createServer } from 'node:net';
import { resolve } from 'node:path';
import { pythonExecutable } from './python.mjs';

if (existsSync('.env')) process.loadEnvFile('.env');
const mode = process.argv[2] || 'dev';
const python = pythonExecutable();
const children = [];
let closing = false;
function stop(code = 0) {
  if (closing) return;
  closing = true;
  for (const child of children) {
    if (!child.pid || child.exitCode !== null) continue;
    if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    else child.kill('SIGTERM');
  }
  process.exitCode = code;
}
function start(command, args, env) {
  const child = spawn(command, args, { stdio: 'inherit', env });
  children.push(child);
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => { if (!closing) stop(code || 0); });
}
async function availablePort(first) {
  for (let candidate = first; candidate < first + 20; candidate++) {
    const free = await new Promise(resolvePort => {
      const server = createServer();
      server.once('error', () => resolvePort(false));
      server.listen(candidate, '127.0.0.1', () => server.close(() => resolvePort(true)));
    });
    if (free) return candidate;
  }
  throw new Error(`No available local port near ${first}`);
}
const env = { ...process.env, PYTHONUNBUFFERED: '1' };
if (mode === 'dev') {
  env.DJANGO_DEBUG = 'true';
  const apiPort = await availablePort(Number(env.DJANGO_PORT || 3001));
  const frontendPort = await availablePort(Number(env.FRONTEND_PORT || 5173));
  env.DJANGO_PORT = String(apiPort);
  env.CSRF_TRUSTED_ORIGINS = [env.CSRF_TRUSTED_ORIGINS, `http://localhost:${frontendPort}`, `http://127.0.0.1:${frontendPort}`].filter(Boolean).join(',');
  const migration = spawnSync(python, ['manage.py', 'migrate', '--noinput'], { stdio: 'inherit', env });
  if (migration.status !== 0) process.exit(migration.status || 1);
  console.log(`AssetCairn frontend: http://localhost:${frontendPort}`);
  start(python, ['manage.py', 'runserver', `127.0.0.1:${apiPort}`], env);
  start(python, ['manage.py', 'reminder_worker'], env);
  start(process.execPath, [resolve('node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', String(frontendPort), '--strictPort'], env);
} else {
  if (env.DJANGO_DEBUG?.toLowerCase() !== 'false' || !env.DJANGO_SECRET_KEY) {
    throw new Error('Production start requires DJANGO_DEBUG=false and a private DJANGO_SECRET_KEY.');
  }
  if (!existsSync('dist/index.html')) throw new Error('Run npm run build before npm start.');
  const port = Number(env.DJANGO_PORT || 3001);
  console.log(`AssetCairn: http://localhost:${port}`);
  start(python, ['-m', 'waitress', '--ident=', `--listen=${env.HOST || '127.0.0.1'}:${port}`, 'backend.wsgi:application'], env);
  start(python, ['manage.py', 'reminder_worker'], env);
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());