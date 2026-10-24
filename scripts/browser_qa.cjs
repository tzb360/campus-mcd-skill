/* Browser-only QA and export. Run after: python -m http.server 8765 --bind 127.0.0.1 --directory docs */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({headless:true, channel:'chrome'});
  const root = path.resolve(__dirname, '..');
  const output = path.join(root, 'docs/assets');
  fs.mkdirSync(output, {recursive:true});
  const logs=[];
  const page = await browser.newPage({viewport:{width:1440,height:1200}, deviceScaleFactor:1});
  page.on('pageerror', error => logs.push(String(error)));
  page.on('console', msg => { if(msg.type()==='error') logs.push(msg.text()); });
  page.on('requestfailed', request => logs.push(request.url()+': '+request.failure().errorText));
  page.on('response', response => { if(response.status()>=400) logs.push(`${response.status()}: ${response.url()}`); });
  await page.goto(process.env.CAMPUS_DEMO_URL || 'http://127.0.0.1:8765/',{waitUntil:'networkidle'});
  await page.getByRole('button',{name:'生成我的课间报告'}).click();
  if(await page.locator('#report article').count()!==3) throw new Error('Missing three policies');
  if(!(await page.locator('#report').innerText()).includes('¥13.90')) throw new Error('Wrong mock quote');
  await page.screenshot({path:path.join(output,'demo-desktop.png'),fullPage:true});
  await page.getByRole('button',{name:'课间 25 分钟 / 不勉强赶'}).click();
  if(await page.locator('#report h2').filter({hasText:'这次，先别赶。'}).count()!==3) throw new Error('Rush should be infeasible');
  await page.screenshot({path:path.join(output,'demo-rush.png'),fullPage:true});
  await page.getByRole('button',{name:'鸡肉偏好 / 700 千卡内'}).click();
  if((await page.locator('#report').innerText()).includes('双堡分享餐')) throw new Error('Calorie/preference constraint failed');
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(output,'demo-mobile.png'),fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error('Mobile horizontal overflow');
  // Exercise each available state through the actual UI, not a second copy of the planner.
  for(const budget of ['10','15','20','25','30']) for(const minutes of ['25','40','60','90']) for(const chicken of ['0','1']) {
    await page.selectOption('#budget',budget); await page.selectOption('#minutes',minutes); await page.selectOption('#chicken',chicken);
    await page.getByRole('button',{name:'生成我的课间报告'}).click();
    if(await page.locator('#report article').count()!==3) throw new Error('State rendering failed');
  }
  await page.setViewportSize({width:320,height:720});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error('320px horizontal overflow');
  await page.keyboard.press('Tab');
  await page.emulateMedia({media:'print'});
  await page.emulateMedia({media:'screen'});
  await page.setViewportSize({width:1120,height:1100});
  await page.goto(new URL('live-example.html', process.env.CAMPUS_DEMO_URL || 'http://127.0.0.1:8765/').href,{waitUntil:'networkidle'});
  if(!(await page.locator('body').innerText()).includes('历史核价样例')) throw new Error('Missing historical data label');
  await page.screenshot({path:path.join(output,'live-history.png'),fullPage:true});
  if(logs.length) throw new Error(logs.join('\n'));
  fs.writeFileSync(path.join(root,'docs/browser-check.json'),JSON.stringify({states:40,viewports:[1440,390,320],consoleErrors:0,failedRequests:0,mode:'mock',browser:await browser.version()},null,2));
  await browser.close();
  process.stdout.write('40 interactive states, 3 widths, screenshot exports: passed; mock data only.\n');
})().catch(error=>{process.stderr.write(String(error)+'\n');process.exit(1)});
