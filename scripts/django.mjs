import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { pythonExecutable } from './python.mjs';

if (existsSync('.env')) process.loadEnvFile('.env');
const env = { ...process.env };
if (env.NODE_ENV === 'production' && env.DJANGO_DEBUG?.toLowerCase() !== 'false') {
	throw new Error('Production Django commands require DJANGO_DEBUG=false.');
}
if (!env.DJANGO_SECRET_KEY && env.NODE_ENV !== 'production') env.DJANGO_DEBUG = 'true';
else env.DJANGO_DEBUG ||= env.NODE_ENV === 'production' ? 'false' : 'true';
const child = spawn(pythonExecutable(), ['manage.py', ...process.argv.slice(2)], { stdio: 'inherit', env });
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });