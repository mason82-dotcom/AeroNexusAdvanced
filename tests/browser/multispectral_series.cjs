// Real DOM checks for the embedded viewer; no live MinIO or DJI connection.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE_PATH,args:process.env.CHROMIUM_ARGS?JSON.parse(process.env.CHROMIUM_ARGS):['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const html=fs.readFileSync(0,'utf8'),ids=['a'.repeat(32),'b'.repeat(32)];
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let handler;
 await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/multispectral')return route.fulfill({contentType:'text/html',body:html});
   if(url.pathname==='/api/v1/multispectral/captures')return route.fulfill({json:{captures:ids.map(id=>({capture_uuid:id,captured_at:'2026-10-15T12:02:40Z',bands:{},warnings:[]}))}});
   if(url.pathname==='/api/v1/multispectral/reports')return handler(route);
   return route.abort();
 });
 await page.goto('http://localhost/multispectral');
 await page.waitForFunction(()=>document.getElementById('report-captures').options.length===2);
 await page.getByRole('button',{name:'Serienbericht berechnen'}).click();
 assert.match(await page.locator('#report-validation').innerText(),/1 bis 20/);
 await page.locator('#report-captures').selectOption(ids);
 await page.locator('#report-mask').check();
 await page.locator('#report-threshold').fill('2');
 await page.locator('#report-run').click();
 assert.equal(await page.locator('#report-threshold').getAttribute('aria-invalid'),'true');
 await page.locator('#report-threshold').fill('0.2');
 const report=body=>({generated_at:'2026-10-17T10:00:00Z',processing_version:'2',scale:body.scale,ndvi_threshold:body.ndvi_threshold,capture_uuids:body.capture_uuids,layers:body.layers,
   rows:body.layers.map(layer=>({capture_uuid:body.capture_uuids[0],captured_at:'2026-10-15T12:02:40Z',layer,status:'ok',warnings:[],stats:{pixels:4,valid_pixels:4,selected_pixels:2,mean:.5,std:.1,median:.5,p10:.4,p90:.6},histogram:{edges:[.4,.5,.6],counts:[1,1]}}))});
 let release,started,calls=0;
 const pending=new Promise(r=>{started=r});
 handler=async route=>{calls++;const body=route.request().postDataJSON();assert.equal(body.ndvi_threshold,.2);started();await new Promise(r=>{release=r});await route.fulfill({json:report(body)});};
 await page.locator('#report-run').click();await pending;
 assert.equal(await page.locator('#report-run').isDisabled(),true);
 assert.equal(await page.locator('#report-captures').isDisabled(),true);
 await page.locator('#report-stop').click();release();
 await page.waitForFunction(()=>!document.getElementById('report-run').disabled);
 assert.equal(calls,1);assert.match(await page.locator('#report-state').innerText(),/Gestoppt.*1 von 2/);
 assert.equal(await page.locator('#report-rows tr').count(),4);
 assert.equal(await page.locator('#report-hist-rows tr').count(),2);
 const download=page.waitForEvent('download');await page.locator('#report-csv').click();
 const csv=await download;assert.match(csv.suggestedFilename(),/teilbericht/);
 const csvText=fs.readFileSync(await csv.path(),'utf8');assert.ok(csvText.startsWith('\ufeffcapture_uuid;'));
 assert.match(csvText,/"0.2"/);
 const jsonDownload=page.waitForEvent('download');await page.locator('#report-json').click();
 const json=JSON.parse(fs.readFileSync(await (await jsonDownload).path(),'utf8'));
 assert.equal(json.completed,false);assert.deepEqual(json.requested_capture_uuids,ids);
 // Changed settings must invalidate every export from the previous settings.
 await page.locator('#report-scale').selectOption('2');assert.equal(await page.locator('#report-csv').isDisabled(),true);
 assert.equal(await page.locator('#report-results').isHidden(),true);
 // A network/permission failure preserves only the completed part.
 calls=0;handler=async route=>{calls++;const body=route.request().postDataJSON();if(calls===2)return route.fulfill({status:503,json:{detail:'Test-Ausfall'}});await route.fulfill({json:report(body)});};
 await page.locator('#report-run').click();
 await page.waitForFunction(()=>!document.getElementById('report-run').disabled);
 assert.match(await page.locator('#report-state').innerText(),/Unterbrochen: Test-Ausfall/);
 assert.equal(await page.locator('#report-csv').isEnabled(),true);
 // Empty masks remain visible and never produce an old histogram.
 handler=async route=>{const r=report(route.request().postDataJSON());r.rows.forEach(row=>{row.status='empty';row.stats.selected_pixels=0;for(const k of ['mean','std','median','p10','p90'])row.stats[k]=null;row.histogram={edges:[],counts:[]};});await route.fulfill({json:r});};
 await page.locator('#report-run').click();await page.waitForFunction(()=>!document.getElementById('report-run').disabled);
 assert.equal(await page.locator('#report-hist-rows tr').count(),0);
 assert.equal(await page.locator('#report-hist-choice').isDisabled(),true);
 assert.match(await page.locator('#report-state').innerText(),/8 leere Auswertungen/);
 // Narrow viewport and keyboard access to result details.
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.ok(await page.evaluate(()=>document.querySelector('aside').getBoundingClientRect().bottom<=document.getElementById('series').getBoundingClientRect().top));
 await page.locator('#report-json').focus();assert.equal(await page.locator('#report-json').evaluate(e=>e===document.activeElement),true);
 assert.deepEqual(errors,[]);
 console.log('Browser: validation, stop/partial, CSV/JSON, invalidation, failure, empty, keyboard and 390px layout passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
