// Prove Pledge end to end on GenLayer Asimov.
//
//   AT=0x... PADV=<padv pw> PPUB=<ppub pw> node scripts/prove.mjs
//
// padv keeps a promise, ppub breaks one, and a promise still in its window cannot
// be judged early. Records accrue to the authors.
import { Wallet } from 'ethers';
import { createClient, createAccount } from 'genlayer-js';
import { testnetAsimov } from 'genlayer-js/chains';
import fs from 'fs';
import os from 'os';
import path from 'path';
import url from 'url';

const AT = process.env.AT;
const PADV = process.env.PADV || '';
const PPUB = process.env.PPUB || '';
if (!AT || !PADV || !PPUB) { console.error('set AT, PADV and PPUB'); process.exit(1); }

const ROOT = path.join(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const KS = path.join(os.homedir(), '.genlayer', 'keystores');
async function acct(file, pw) {
  const w = await Wallet.fromEncryptedJson(fs.readFileSync(path.join(KS, file), 'utf8'), pw);
  return { addr: w.address.toLowerCase(), client: createClient({ chain: testnetAsimov, account: createAccount(w.privateKey) }) };
}
const padv = await acct('padv.json', PADV);
const ppub = await acct('ppub.json', PPUB);
const anybody = createClient({ chain: testnetAsimov });

const RAW = 'https://raw.githubusercontent.com/JspIIV/pledge-board/master/docs/';
const PAST = '1700000000';
const FUTURE = String(Math.floor(Date.now() / 1000) + 100000);
const KEPT_P = { commitment: 'We will release v2.3.1 with the security fix.', url: RAW + 'release-shipped.txt' };
const BROKEN_P = { commitment: 'We will launch a public token sale by Q3.', url: RAW + 'no-token-sale.txt' };

const out = [];
const say = l => { console.log(l); out.push(l); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const transient = e => /-32005|-32006|-32029|-32603|at capacity|rate limit|gas rate|reverted.*consensus|consensus.*reverted|backpressure|fetch failed|timeout|502|503|429|ECONNRESET|ENOTFOUND|EAI_AGAIN|getaddrinfo/i
  .test(String(e?.details || e?.shortMessage || e?.message || e) + " " + String(e?.cause?.cause?.code || e?.cause?.code || ""));

async function read(fn, args = []) {
  for (let a = 1; ; a++) {
    try { return JSON.parse(await anybody.readContract({ address: AT, functionName: fn, args })); }
    catch (e) { if (!transient(e) || a >= 8) throw e; await sleep(4000 * a); }
  }
}
async function write(who, fn, args) {
  for (let a = 1; ; a++) {
    try { return await who.client.writeContract({ address: AT, functionName: fn, args, value: 0n }); }
    catch (e) { if (!transient(e) || a >= 8) throw e; say(`  (${fn} transient, wait ${8 * a}s)`); await sleep(8000 * a); }
  }
}
async function makePledge(who, p, due) {
  const n = (await read('size')).total;
  await write(who, 'pledge', [p.commitment, p.url, due]);
  for (let i = 0; i < 20; i++) { const s = await read('size'); if (s.total > n) return String(s.total - 1); await sleep(4000); }
  throw new Error('pledge not made');
}
async function checkUntilJudged(id, label) {
  for (let attempt = 1; attempt <= 4; attempt++) {
    let g = await read('get', [id]);
    if (g.status === 'KEPT' || g.status === 'BROKEN') { say(`  ${label}: already ${g.status}`); return g; }
    try { await write(padv, 'check', [id]); } catch (e) { say(`  ${label} check err ${String(e.message).slice(0, 50)}`); }
    for (let i = 0; i < 36; i++) {
      await sleep(15000);
      g = await read('get', [id]);
      if (g.status === 'KEPT' || g.status === 'BROKEN') { say(`  ${label}: ${g.status} (${(i + 1) * 15}s)`); return g; }
    }
    say(`  ${label}: not judged after poll, retrying`);
  }
  return await read('get', [id]);
}

say('Pledge, proven on GenLayer Asimov');
say('  contract ' + AT);
say('  padv ' + padv.addr + '  ppub ' + ppub.addr);
say('');

const id0 = await makePledge(padv, KEPT_P, PAST);
say('padv pledged #' + id0 + ' (a promise its source shows kept)');
const id1 = await makePledge(ppub, BROKEN_P, PAST);
say('ppub pledged #' + id1 + ' (a promise its source shows broken)');
const id2 = await makePledge(padv, KEPT_P, FUTURE);
say('padv pledged #' + id2 + ' (deadline in the future)');
say('');

say('checking #' + id0 + '...');
const r0 = await checkUntilJudged(id0, 'pledge0');
say('  status ' + r0.status + ' | ' + (r0.reason || ''));
say('checking #' + id1 + '...');
const r1 = await checkUntilJudged(id1, 'pledge1');
say('  status ' + r1.status + ' | ' + (r1.reason || ''));
say('');

say('trying to check #' + id2 + ' before its deadline...');
try { await write(padv, 'check', [id2]); } catch {}
await sleep(6000);
const r2 = await read('get', [id2]);
say('  #' + id2 + ' status after early check: ' + r2.status);
say('');

const recPadv = await read('record', [padv.addr]);
const recPpub = await read('record', [ppub.addr]);
const size = await read('size');
say('record(padv) = ' + JSON.stringify(recPadv) + ' ; record(ppub) = ' + JSON.stringify(recPpub));
say('register: ' + JSON.stringify(size));

const checks = [
  ['a kept promise is judged KEPT', r0.status === 'KEPT'],
  ['a broken promise is judged BROKEN', r1.status === 'BROKEN'],
  ["the keeper's record shows the kept promise", recPadv.kept >= 1],
  ["the breaker's record shows the broken promise", recPpub.broken >= 1],
  ['a promise cannot be checked before its deadline, it stays pending', r2.status === 'PENDING'],
  ['the register counts one kept and one broken', size.kept === 1 && size.broken === 1],
];
say('');
for (const [label, ok] of checks) say((ok ? '  ok   ' : ' FAIL  ') + label);
const failed = checks.filter(([, ok]) => !ok);
say('');
say(failed.length ? `${failed.length} of ${checks.length} checks failed` : `${checks.length} checks. The source judged the promise, and the record remembered.`);

fs.mkdirSync(path.join(ROOT, 'results'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'results', 'proved.json'), JSON.stringify({
  proved_at: new Date().toISOString(), network: 'genlayer testnet asimov', contract: AT,
  kept: r0, broken: r1, early: r2, record: { padv: recPadv, ppub: recPpub }, size,
  checks: checks.map(([label, ok]) => ({ label, ok })), transcript: out,
}, null, 2));
say('Written to results/proved.json');
process.exit(failed.length ? 1 : 0);
