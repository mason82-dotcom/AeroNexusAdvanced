"""Run the real embedded series controller, including async stop/failure handling."""
import re
import shutil
import subprocess

import pytest

from aeronexus.multispectral_page import render_multispectral_page
from test_multispectral_browser_js import RUNTIME


SCRIPT = RUNTIME.split('(async()=>{', 1)[0].replace(
    ' load,quadPoint,drawOverlays,',
    ''' runReport,invalidateReport,reportCsvCell,
 report(){return seriesReport;}, stop(){reportStopping=true;},
 load,quadPoint,drawOverlays,''').replace(
    'const app=new Function',
    '''Element.prototype.focus=function(){};
Object.defineProperty(Element.prototype,'firstChild',{get(){return this.children[0];}});
Object.defineProperty(Element.prototype,'options',{get(){return this.children;}});
const fields=[{value:'ndvi'},{value:'ndre'}];
document.querySelectorAll=selector=>selector.includes('report-indices')?fields:[];
const app=new Function''') + r'''
(async()=>{
 $('report-captures').selectedOptions=[];
 await app.runReport();assert.match($('report-validation').textContent,/1 bis 20/);
 const ids=['a'.repeat(32),'b'.repeat(32)];
 $('report-captures').selectedOptions=ids.map(value=>({value}));
 $('report-scale').value='4';$('report-mask').checked=true;$('report-threshold').value='2';
 await app.runReport();assert.equal($('report-threshold')['aria-invalid'],'true');
 $('report-threshold').value='0.2';
 const result=id=>({processing_version:'2',scale:4,ndvi_threshold:.2,capture_uuids:[id],
 rows:[{capture_uuid:id,captured_at:null,layer:'ndvi',status:'ok',warnings:[],
 stats:{selected_pixels:2,valid_pixels:4,mean:.5},histogram:{edges:[0,.5,1],counts:[1,1]}}]});
 const pending=deferred();let calls=0;
 app.mock(async(p,b,options)=>{calls++;const request=JSON.parse(options.body);assert.equal(request.ndvi_threshold,.2);return pending.promise;});
 const running=app.runReport();assert.equal($('report-run').disabled,true);
 assert.equal($('report-settings').disabled,true);assert.equal($('report-json').disabled,true);
 // A duplicate start must not issue another request.
 await app.runReport();assert.equal(calls,1);
 app.stop();pending.resolve(result(ids[0]));await running;
 assert.equal(calls,1);assert.equal(app.report().completed,false);
 assert.deepEqual(app.report().requested_capture_uuids,ids);
 assert.equal($('report-csv').disabled,false);assert.match($('report-state').textContent,/Gestoppt/);
 assert.equal($('report-hist-rows').children.length,2);
 app.invalidateReport();assert.equal(app.report(),null);assert.equal($('report-json').disabled,true);
 // Failure after one capture retains only that completed result.
 calls=0;app.mock(async()=>{if(++calls===2)throw Error('offline');return result(ids[0]);});
 await app.runReport();assert.equal(app.report().rows.length,1);
 assert.match($('report-state').textContent,/Unterbrochen: offline/);
 // Empty results clear old histograms; all-error results are still exportable.
 app.mock(async()=>{const r=result(ids[0]);r.rows[0].status='empty';r.rows[0].histogram={edges:[],counts:[]};return r;});
 await app.runReport();assert.equal($('report-hist-rows').children.length,0);
 assert.equal($('report-hist-choice').disabled,true);assert.equal(app.report().completed,true);
 app.mock(async()=>{throw Error('permission denied');});await app.runReport();
 assert.equal(app.report(),null);assert.equal($('report-csv').disabled,true);
 assert.equal(app.reportCsvCell(' =1+1'),'"\' =1+1"');
 assert.equal(app.reportCsvCell(-3.5),'"-3.5"');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''


def test_series_controller_validation_stop_exports_failure_and_empty():
    if shutil.which('node') is None:
        pytest.skip('Node.js required for embedded controller checks')
    script, = re.findall(r'<script>(.*?)</script>', render_multispectral_page(), re.S)
    result = subprocess.run(['node','-e', SCRIPT], input=script, text=True,
                            capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
