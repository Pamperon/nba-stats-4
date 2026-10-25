/* Test-only PostgreSQL-in-WASM bridge. In-memory data, no listening socket. */
const {PGlite} = require('@electric-sql/pglite');
const readline = require('node:readline');
(async () => {
  const db = await PGlite.create({parsers: {1082: value => value, 1184: value => value}});
  const input = readline.createInterface({input: process.stdin});
  for await (const line of input) {
    try {
      const request = JSON.parse(line);
      if (request.close) {await db.close(); input.close(); process.stdin.destroy(); return;}
      const result = await db.query(request.sql, request.params || [], {rowMode: 'array'});
      process.stdout.write(JSON.stringify(result, (_, value) => typeof value === 'bigint' ? Number(value) : value) + '\n');
    } catch (error) {
      process.stdout.write(JSON.stringify({error: error.message}) + '\n');
    }
  }
})().catch(error => {process.stderr.write(String(error)); process.exitCode = 1;});
