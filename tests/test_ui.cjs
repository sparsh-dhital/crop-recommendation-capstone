const {JSDOM, VirtualConsole} = require('jsdom');
const assert = require('node:assert/strict');
(async () => {
  const url=process.env.CROP_TEST_URL || 'http://127.0.0.1:5051';
  let cookie='';
  const errors=[];
  const request = async (path, options={}) => {
    const response=await fetch(new URL(path,url), {...options,headers:{...options.headers, Cookie:cookie}});
    const next=response.headers.get('set-cookie');
    if(next) cookie=next.split(';')[0];
    return response;
  };
  const html=await (await request('/login')).text();
  const console = new VirtualConsole();
  console.on('jsdomError', e => errors.push(e.message));
  const dom=new JSDOM(html,{url:url+'/login',runScripts:'dangerously',virtualConsole:console,
    beforeParse(window) { window.fetch=request; window.scrollTo=()=>{}; }});
  const w=dom.window, d=w.document;
  const fill=(id,value)=>{d.getElementById(id).value=value;};
  const until=async predicate=>{
    for(let i=0;i<100;i++) { if(predicate())return; await new Promise(r=>setTimeout(r,20)); }
    throw new Error('Timed out waiting for UI state');
  };
  await until(()=>!d.getElementById('authSubmit').disabled);
  assert(d.getElementById('login').classList.contains('active'));
  const username='ui_'+Date.now();
  const password='temporary test password';
  d.getElementById('authToggle').click();
  assert.equal(d.getElementById('authTitle').textContent,'Create Account');
  fill('loginUser',username);fill('loginPass',password);fill('confirmPass','mismatch password');
  d.getElementById('authSubmit').click();
  await until(()=>!d.getElementById('authSubmit').disabled);
  assert.equal(d.getElementById('loginErrorText').textContent,'Passwords do not match.');
  fill('confirmPass',password);d.getElementById('authSubmit').click();
  await until(()=>d.getElementById('predict').classList.contains('active'));
  assert.equal(d.getElementById('navUser').textContent,username);
  const values={Nitrogen:90,Phosphorus:42,Potassium:43,Temperature:20.5,Humidity:82,Ph:6.5,Rainfall:200};
  for(const [key,value] of Object.entries(values))d.querySelector(`[name="${key}"]`).value=value;
  d.getElementById('btnPredict').click();
  await until(()=>d.getElementById('result').classList.contains('active'));
  assert.equal(d.getElementById('cropName').textContent,'rice');
  assert.equal(JSON.parse(w.localStorage.getItem('crop_history_'+username))[0].crop,'rice');
  // Logout through the visible result view and confirm its session is revoked.
  d.querySelector('#result .btn-logout').click();
  await until(()=>d.getElementById('landing').classList.contains('active'));
  assert.equal((await (await request('/api/session')).json()).username,null);
  d.querySelector('.btn-glow').click();
  d.getElementById('authToggle').click();
  fill('loginUser',username);fill('loginPass','incorrect password');
  d.getElementById('authSubmit').click();
  await until(()=>!d.getElementById('authSubmit').disabled);
  assert.equal(d.getElementById('loginErrorText').textContent,'Incorrect username or password.');
  fill('loginPass',password);d.getElementById('authSubmit').click();
  await until(()=>d.getElementById('predict').classList.contains('active'));
  assert.equal((await (await request('/api/session')).json()).username,username);
  assert.equal(w.localStorage.getItem('crop_users_registry'),null);
  assert.equal(w.localStorage.getItem('crop_logged'),null);
  assert.deepEqual(errors,[]);
  dom.window.close();
  process.stdout.write('PASS: rendered-page DOM integration against Flask: registration mismatch, registration, rice prediction, saved history, logout, wrong password, successful login; no JavaScript errors.\n');
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exit(1);});
