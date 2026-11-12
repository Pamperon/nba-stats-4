const test = require('node:test');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {PGlite} = require('@electric-sql/pglite');

test('slot recovery is atomic, bounded, and respects active jobs and completed slots', async () => {
  const source = execFileSync('python', ['-c', `import ast,json
t=ast.parse(open('storage.py').read())
f=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='claim_slot')
print(json.dumps(next(n.value for n in ast.walk(f) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'INSERT INTO nba_scan_slots' in n.value)))`], {encoding:'utf8'});
  let i=0;
  const sql=JSON.parse(source).replaceAll('%s', () => '$'+(++i));
  const db=await PGlite.create();
  try {
    await db.exec(`CREATE TABLE nba_scan_slots(slot_key text PRIMARY KEY,status text,
      claimed_at timestamptz DEFAULT NOW(),heartbeat_at timestamptz,finished_at timestamptz,
      instance_id text,recovery_count integer DEFAULT 0);
      CREATE TABLE nba_scan_attempts(slot_key text,state text,heartbeat_at timestamptz);`);
    const claim=async key=>(await db.query(sql,[key,'runtime'])).rows.length;
    const stale=async key=>db.query("UPDATE nba_scan_slots SET heartbeat_at=NOW()-INTERVAL '3 minutes' WHERE slot_key=$1",[key]);
    assert.equal(await claim('a'),1);
    assert.equal(await claim('a'),0);
    await stale('a');
    await db.exec("INSERT INTO nba_scan_attempts VALUES('a','running',NOW())");
    assert.equal(await claim('a'),0);
    await db.exec("UPDATE nba_scan_attempts SET heartbeat_at=NOW()-INTERVAL '3 minutes'");
    assert.equal(await claim('a'),1);
    await stale('a');
    assert.equal(await claim('a'),0);
    await claim('done');
    await stale('done');
    await db.exec("UPDATE nba_scan_slots SET status='done' WHERE slot_key='done'");
    assert.equal(await claim('done'),0);
    await claim('failed');
    await stale('failed');
    await db.exec("UPDATE nba_scan_slots SET status='failed' WHERE slot_key='failed'");
    assert.equal(await claim('failed'),1);
    assert.equal(await claim('failed'),0);
  } finally { await db.close(); }
});
