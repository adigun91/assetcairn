import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

export function pythonExecutable() {
  const executable = process.env.PYTHON_EXECUTABLE || resolve('.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  if (!existsSync(executable)) throw new Error('Project Python environment is missing. Create .venv and install requirements.txt first.');
  return executable;
}