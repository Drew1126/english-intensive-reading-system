/* Headless integration against the real page; synthetic SSE, isolated browser profile. */
const assert = require('assert');
const fs = require('fs');
const {chromium} = require('playwright');
(async () => {
 let data=JSON.parse(fs.readFileSync('frontend/preview-reveal-data.json','utf8'));
 if (process.argv.includes('--live-result')) {
  const result=JSON.parse(fs.readFileSync('tmp/structure-reveal-production.json','utf8'));
  data={sentence:result.core.sentence,answer:result.text,core:result.core};
 }
 if (process.argv.includes('--split-clause')) {
  const phrase='in which organizations and officials use the power of group dynamics';
  data.answer=data.answer.replace('\n'+phrase+'\n','\n**in which** 指代 the social cure。\n\n'+phrase.slice('in which '.length)+'\n');
 }
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage(); const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/agent/ask?**',route=>route.fulfill({status:200,contentType:'text/event-stream',body:'data: '+JSON.stringify({text:data.answer,core:data.core})+'\n\ndata: [DONE]\n\n'}));
  await page.goto('http://127.0.0.1:8001/',{waitUntil:'networkidle'});
  await page.evaluate(data=>{
   window.getToken=()=> 'isolated-browser-test'; window.getName=()=> 'test';
   reviewModule.recordAnswer=()=>{};
   document.getElementById('loginOverlay').style.display='none';
   document.body.classList.remove('home-active');
   articleModule.currentArticle={id:'reveal-browser-test',title:'交互回归测试'};
   articleModule.editing=false; articleModule.focusWords=[];
   const el=document.createElement('span');el.className='sentence selected';el.dataset.idx='0-0';el.textContent=data.sentence;
   document.getElementById('articleBody').replaceChildren(el);
   articleModule.selectedSentenceIdx='0-0'; window.__currentIdx='0-0';
   agentModule.showSelectedSentence(data.sentence,'0-0');
   agentModule.streamAnswer(data.sentence,'解释句子结构','reveal-browser-test','');
  },data);
  await page.waitForSelector('.reveal-fragment');
  const buttons=page.locator('.reveal-fragment'); assert.equal(await buttons.count(),5);
  const background=buttons.filter({hasText:'in her new book'}), way=buttons.filter({hasText:'through what'}), clause=buttons.filter({hasText:'organizations and officials'}), help=buttons.filter({hasText:'to help individuals'}), action=buttons.filter({hasText:'improve their lives'});
  if (process.argv.includes('--split-clause')) {
   assert.equal(await page.locator('.reveal-extra').count(),0);
   assert.equal(await clause.textContent(),'organizations and officials use the power of group dynamics');
   assert((await clause.getAttribute('aria-label')).startsWith('in which organizations'));
  }
  assert(await clause.isDisabled()); assert(await help.isDisabled()); assert(await action.isDisabled());
  const original=await page.locator('#articleBody').textContent();
  const font=await page.locator('#articleBody .sentence').evaluate(el=>({family:getComputedStyle(el).fontFamily,size:getComputedStyle(el).fontSize}));
  await background.click(); await way.click(); assert(await clause.isEnabled());
  await clause.click(); assert(await help.isEnabled());
  assert.equal(await page.evaluate(()=>CSS.highlights.get('sentence-reference').size),2);
  assert((await page.locator('.reveal-status').textContent()).includes('the social cure'));
  await help.click(); await action.click();
  const actionNode=data.core.reveal.nodes.find(n=>n.text.includes('improve their lives'));
  if (actionNode.references.length) assert((await page.locator('.reveal-status').textContent()).includes(actionNode.references[0].target));
  else assert.equal(await page.evaluate(()=>CSS.highlights.has('sentence-reference')),false);
  await way.click(); assert(await clause.isDisabled()); assert(await help.isDisabled()); assert(await action.isDisabled());
  assert.equal(await background.getAttribute('aria-pressed'),'true');
  assert.equal(await page.evaluate(()=>CSS.highlights.has('sentence-reference')),false);
  assert.equal(await page.locator('#articleBody').textContent(),original);
  assert.deepEqual(await page.locator('#articleBody .sentence').evaluate(el=>({family:getComputedStyle(el).fontFamily,size:getComputedStyle(el).fontSize})),font);
  await page.locator('#structureFocusToggle').click(); assert.equal(await page.locator('.structure-muted').count(),0);
  await way.click(); assert((await page.locator('.structure-muted').count())>0);
  await clause.click(); await page.evaluate(()=>document.documentElement.dataset.theme='dark');
  assert.equal(await page.evaluate(()=>CSS.highlights.get('sentence-reference').size),2);
  await page.screenshot({path:'tmp/reveal-system-browser.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert(await way.isEnabled());
  await page.evaluate(()=>{articleModule.currentArticle={id:'another'};structureFocus.sync()});
  assert(await way.isDisabled()); assert.equal(await page.evaluate(()=>CSS.highlights.has('sentence-reference')),false);
  assert.deepEqual(errors,[]);
  console.log('PASS: real main page + SSE, inline links, locks, reference highlights, cascade collapse, independent background, font/text preservation, dark/mobile and article switch');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
