# 赛事核验与差异化记录

核验日期：北京时间2026-10-24。官方源代码读取点：

- 初始规则核验commit `22913d4683d56119310206b95636386c7cbdd805`；最新榜单commit `2f79d225260ddd63c03dd27072ba36d899deeb5f`，更新时间2026-10-24 21:00:54。
- MCP文档commit `e90ecc5c918f307ff5f997caa73e4d60bef375e9`。
- [活动主页](https://github.com/M-China/mcd-developer-innovation-challenge)
- [完整规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)
- [榜单](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/RANKING.md)
- [MCP官方文档](https://github.com/M-China/mcd-mcp-server)

## 资格与提交

官方时间：报名截止2026-10-25 23:59；最终排名按2026-10-26 00:00采集数据。项目创建时间须在2025-12-25 00:00至报名截止之间，发布于个人账户Public开源仓库，并保持公开访问。参与者须符合规则所列中国大陆合法居民及年龄/监护人同意条件；具体身份由本人确认，代码不能代为证明。

必须文件：README.md、官方原文CONTEST_DECLARATION.md、MCP_INTEGRATION.md、只含环境变量占位符的mcp-config.example.json、可运行内容。须真实使用麦当劳MCP。WorkBuddy不是普通排名参赛的必选项；专项奖励需真实使用及workbuddy.md，不可伪造。本项目尚未使用WorkBuddy。

将标准格式报名Issue发到官方仓库：每个字段名与内容同一行，项目地址使用裸URL。官方回复成功才算报名接收；榜单展示不代表资格/获奖最终审核通过。相同账号多项目只取最高Star项目；零Star不入榜；第100个项目同分者一并展示。

最新已核验榜单第98–100个项目均为51 Star，**当前门槛51**，不能当作最终门槛或达标承诺。合法传播应获取真实用户认可，不做刷Star或交换虚假互动。获奖后应留意GitHub邮箱/OAuth通知，按官方链路在11月14日前提供领奖所需信息；公开Issue不要填写手机号和住址。

## 已有作品审查（仅阅读公开README，未复用实现/素材）

| 作品 | README所述方向 | 对本项目定位的影响 |
|---|---|---|
| [Sam-Hui-dot/mcd-budget-meal](https://github.com/Sam-Hui-dot/mcd-budget-meal) | 预算与偏好、候选核价、交互报告 | 单纯预算比较及报告不足以区分 |
| [Penk-git/mcd-campus-combo](https://github.com/Penk-git/mcd-campus-combo) | 多种校园场景、凑单、营养、网页 | 不声称校园主题首次出现 |
| [erikzeng2008-del/mcd-dual-budget-coach](https://github.com/erikzeng2008-del/mcd-dual-budget-coach) | 预算与热量、三档推荐、人设卡 | 热量约束和趣味卡已有同类 |
| [wusuaya/overtime-meal-buddy](https://github.com/wusuaya/overtime-meal-buddy) | 多人需求、团餐分配和分账 | 本项目聚焦单人返课截止时间 |

只读审查帮助识别同质化，不据此声称上述项目具体实现均经过验证。没有进行全量参赛项目代码审计，也不能保证没有其他相似方向。

本项目自己的可核验重点：返回deadline作为硬约束、原路双程步行、明确出餐假设、晚出发缩短窗口、缓冲与余量、无法核实不推荐、ICS单次事件空档、同一个Python内核生成CLI与静态演示、默认脱敏报告。不是声称世界首创。

## 状态

本地代码、模拟验收、官方真实工具发现及只读整单核价已完成。未创建Public仓库、未报名、未取得官方审核结果。完整操作草案见[release-checklist.md](release-checklist.md)。
