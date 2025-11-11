import { spawn } from 'child_process';

const PYTHON_BIN = process.env.PYTHON_BIN || 'python3';

function normalizePayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return {};
  }
  return payload;
}

export function runScraperOp(operation, payload = {}) {
  const input = JSON.stringify(normalizePayload(payload));
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, ['scrape_cli.py', operation], {
      cwd: process.cwd(),
      env: process.env,
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', chunk => {
      stdout += chunk.toString();
    });

    proc.stderr.on('data', chunk => {
      stderr += chunk.toString();
    });

    proc.on('error', reject);

    proc.on('close', code => {
      const text = stdout.trim();
      if (!text) {
        if (code === 0) {
          resolve({});
        } else {
          resolve({ error: stderr.trim() || `exit ${code}` });
        }
        return;
      }
      try {
        const parsed = JSON.parse(text);
        if (code === 0) {
          resolve(parsed);
        } else if (parsed && typeof parsed === 'object') {
          resolve({ ...parsed, error: parsed.error || stderr.trim() || `exit ${code}` });
        } else {
          resolve({ error: stderr.trim() || text || `exit ${code}` });
        }
      } catch (err) {
        if (code === 0) {
          reject(new Error(`Invalid JSON from scraper: ${err.message}`));
        } else {
          resolve({ error: stderr.trim() || text || `exit ${code}` });
        }
      }
    });

    try {
      proc.stdin.write(input);
    } catch (err) {
      proc.kill('SIGTERM');
      reject(err);
      return;
    }
    proc.stdin.end();
  });
}

export default runScraperOp;
