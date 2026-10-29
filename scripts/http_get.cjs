/* 單次HTTPS GET。預設TLS驗證、無登入、無重新導向、無持久Cookie。 */
const https = require('node:https');
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0,'utf8'));
const url = new URL(input.url);
if(url.protocol!=='https:' || url.username || url.password || (url.port && url.port!=='443')) throw new Error('HTTPS required');
const limit=input.limit;
if(!Number.isInteger(limit) || limit<1 || limit>10*1024*1024) throw new Error('Invalid byte limit');
const request=https.get(url,{agent:false,rejectUnauthorized:true,headers:input.headers},response=>{
 const chunks=[];let size=0;
 response.on('data',chunk=>{size+=chunk.length;if(size>limit){response.destroy(new Error('response_too_large'));return;}chunks.push(chunk);});
 response.on('error',error=>{process.stderr.write(error.code||'response_error');process.exitCode=1;});
 response.on('end',()=>{
  if(size>limit) return;
  const headers={};
  for(const key of ['content-type','etag','last-modified','location','retry-after']) if(response.headers[key]) headers[key]=response.headers[key];
  process.stdout.write(JSON.stringify({status:response.statusCode,headers,body:Buffer.concat(chunks).toString('base64')}));
 });
});
request.setTimeout(20000,()=>request.destroy(new Error('request_timeout')));
request.on('error',error=>{process.stderr.write(error.code||'request_error');process.exitCode=1;});
