'use strict';
const fields = ['budget', 'minutes', 'chicken'].map(id => document.getElementById(id));
function generate() {
  const key = fields.map(f => f.value).join('-');
  const content = window.CAMPUS_DEMO[key];
  if (!content) {
    document.getElementById('status').textContent = '没有对应的模拟状态，请重新选择。';
    return;
  }
  // Only repository-built, escaped mock reports; never server/user content.
  document.getElementById('report').innerHTML = content;
  document.getElementById('status').textContent = `模拟报告已生成：${fields[0].value} 元，${fields[1].value} 分钟。`;
}
document.getElementById('settings').addEventListener('submit', event => { event.preventDefault(); generate(); });
for (const button of document.querySelectorAll('[data-scene]')) {
  button.addEventListener('click', () => {
    button.dataset.scene.split('-').forEach((value, i) => { fields[i].value = value; });
    generate();
  });
}
document.getElementById('print').addEventListener('click', () => window.print());
generate();
