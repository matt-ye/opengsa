/* 端到端測試用假傳輸：測試會把它蓋到 repo 副本的 scripts/http_get.cjs，介面同原檔，只讀本機假頁，不連外。 */
const fs = require('node:fs');
const path = require('node:path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dir = process.env.OPENGSA_FIXTURES;
const map = JSON.parse(fs.readFileSync(path.join(dir, 'map.json'), 'utf8'));
fs.appendFileSync(path.join(dir, 'requests.log'), input.url + '\n');
const hit = map[input.url];
const body = hit ? fs.readFileSync(path.join(dir, hit)) : Buffer.alloc(0);
const type = hit ? 'text/html; charset=utf-8' : 'text/plain';
process.stdout.write(JSON.stringify({ status: hit ? 200 : 404, headers: { 'content-type': type }, body: body.toString('base64') }));
