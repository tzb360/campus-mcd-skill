# 贡献指南

先运行`python -m pip install -e '.[dev]'`、`python -m pytest -q`和`ruff check src tests scripts`。新功能请附能复现行为的最小例子和必要测试，明确模拟/本地协议/真实官方服务三种验证边界。

欢迎贡献ICS循环事件展开、真正的路线来源适配、跨店候选筛选与无障碍改进。不要提交真实Token、手机号、精确地点、会员券号或原始官方返回；测试用虚构数据。发现安全问题请先避免公开敏感细节，由维护者设置私密报告渠道后提交。请勿引入订单创建、自动领券、支付和积分消费。

截图重建：`python scripts/build_demo.py`，从`docs/`启动本地HTTP服务后运行`scripts/browser_qa.cjs`（需安装Playwright及浏览器）。网页展示使用Python预计算的40组mock结果，不另写一套价格算法；修改规划逻辑后重新生成。

项目欢迎真实体验与理性反馈，禁止刷Star、互刷、机器人、批量账号及虚假互动。
