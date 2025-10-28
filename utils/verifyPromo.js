import { spawn } from 'child_process';

const PYTHON_BIN = process.env.PYTHON_BIN || 'python3';
const VERIFY_LIMIT = Number(process.env.VERIFY_PROMO_SCRAPE_LIMIT || 50);

function runPython(op, payload) {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, ['scrape_cli.py', op], {
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
      if (code === 0) {
        try {
          const json = JSON.parse(stdout || '{}');
          resolve(json);
        } catch (err) {
          reject(new Error(`Invalid JSON from scraper: ${err.message}`));
        }
      } else {
        const message = stderr || stdout || `exit ${code}`;
        resolve({ error: message });
      }
    });

    try {
      proc.stdin.write(JSON.stringify(payload || {}));
    } catch (err) {
      proc.kill('SIGTERM');
      reject(err);
      return;
    }
    proc.stdin.end();
  });
}

function normalizeDomain(domain) {
  return String(domain || '')
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '');
}

function normalizeCode(code) {
  return String(code || '')
    .trim()
    .toUpperCase();
}

function extractCodes(codes) {
  if (!Array.isArray(codes)) return [];
  const seen = new Set();
  const list = [];
  for (const item of codes) {
    const c = typeof item === 'string' ? item : item?.code;
    if (!c) continue;
    const normalized = normalizeCode(c);
    if (!normalized) continue;
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    list.push({ code: normalized, raw: item });
  }
  return list;
}

export async function verifyPromo(domain, code) {
  const normalizedDomain = normalizeDomain(domain);
  const normalizedCode = normalizeCode(code);

  if (!normalizedDomain) {
    return { valid: false, error: 'domain required' };
  }
  if (!normalizedCode) {
    return { valid: false, error: 'code required' };
  }

  try {
    const { codes: scrapedCodes = [], error } = await runPython('codes', {
      domain: normalizedDomain,
      limit: VERIFY_LIMIT,
    });

    if (error) {
      return { valid: false, error };
    }

    const extracted = extractCodes(scrapedCodes);
    const match = extracted.find(entry => entry.code === normalizedCode);

    if (match) {
      return {
        valid: true,
        domain: normalizedDomain,
        code: normalizedCode,
        source: 'scrape',
      };
    }

    return {
      valid: false,
      domain: normalizedDomain,
      code: normalizedCode,
      reason: 'code not found in scrape results',
    };
  } catch (err) {
    return { valid: false, error: err.message };
  }
}

export default verifyPromo;
