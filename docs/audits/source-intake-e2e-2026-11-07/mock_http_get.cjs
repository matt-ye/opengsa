/* 離線假傳輸：取代 repo 副本裡的 scripts/http_get.cjs。介面同原檔，只讀本機假頁，不連外。 */
const fs = require('node:fs');
const path = require('node:path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const dir = process.env.OPENGSA_FIXTURES;
const map = JSON.parse(fs.readFileSync(path.join(dir, 'map.json'), 'utf8'));
fs.appendFileSync(path.join(dir, 'requests.log'), input.url + '\n');
const hit = map[input.url];
if (!hit) {
  process.stdout.write(JSON.stringify({ status: 404, headers: { 'content-type': 'text/plain' }, body: '' }));
} else {
  const body = fs.readFileSync(path.join(dir, hit.file));
  process.stdout.write(JSON.stringify({ status: 200, headers: { 'content-type': hit.type }, body: body.toString('base64') }));
}
