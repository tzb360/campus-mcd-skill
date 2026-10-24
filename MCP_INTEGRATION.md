# 麦当劳 MCP 接入与验证边界

服务：`https://mcp.mcd.cn`，Streamable HTTP，Authorization Bearer。申请入口：https://open.mcd.cn/mcp 。官方工具说明：https://github.com/M-China/mcd-mcp-server 。本项目使用官方 Python MCP SDK 1.x（最低1.30，固定<2）处理会话、初始化、工具发现、分页与调用，使用httpx超时和JSON Schema参数校验。

## 实际实现

`src/campus_mcd/mcp_client.py` 实现真实网络客户端，`official.py`实现实际联调过的自动到店自取适配，`live.py` 实现Agent提供响应字段映射的整单核价流程，`planner.py`负责本地约束比较。先执行`initialize`及`tools/list`，再校验本次发现的inputSchema；不内置猜测的官方参数。工具名白名单：

| 官方文档工具 | 本项目用途 |
|---|---|
| query-nearby-stores | 用户指定地点附近门店，取最多3店 |
| query-meals | 当前门店可售菜单，缩减候选 |
| query-meal-detail | 完整套餐与必要规格，核验偏好 |
| list-nutrition-foods | 精确匹配整餐或组成，未知不通过热量硬限制 |
| query-my-coupons | 用户授权查看的已有券 |
| query-store-coupons | 当前门店适用券 |
| calculate-price | 每份完整候选的本轮应付总价，可另做同单无券对照 |
| campaign-calendar | 活动背景提示，不代替报价 |

未发现的工具停止调用。`create-order`、`auto-bind-coupons`、积分消费等工具即便被发现也不能从本项目调用。每次live进程最多32次业务调用，其中12次核价，含对照；不做无界组合搜索，不自动重试429/业务错误。独立`call`命令用于Agent调试时，Agent应控制整轮总量。

实时数据流程：位置与期限 → 工具发现 → 门店/菜单/详情/营养/已有券 → Agent筛选完整候选与实际参数 → `live`重新发现/校验 → 重新整单试算 → JSON Pointer提取金额/名称 → 金额分与时间约束比较 → A/B/C报告。

官方公开README列出了工具名称与用途，没有公开每个工具的完整inputSchema和结果schema。本轮真实工具发现已取得完整schema，`live-auto`据此实现明确适配：storeCode/orderType=1/beType=1、套餐roundList、默认特调、实际data.price整数分。它每次仍发现/校验schema；复杂情况由Agent解释实际描述与返回值，再使用明确来源映射。配方格式见[docs/live-recipe.md](docs/live-recipe.md)。没有Token时不编造这些字段。

## 本地配置

使用系统/终端环境变量`MCD_MCP_TOKEN`（不放进命令历史、前端或仓库）。也支持私有文件：

1. 从官方平台申请Token，在本机编辑`private/mcd-token.txt`，不要发到聊天。
2. macOS/Linux执行`chmod 600 private/mcd-token.txt`；Windows请用当前用户专用ACL。
3. `campus-mcd discover --output private/tools.json`。
4. 使用`live-auto`自动到店自取流程，或由Agent读取schema后执行`call`与`live`。

可用`CAMPUS_MCD_TOKEN_FILE`指定另一私有文件、`CAMPUS_MCD_TIMEOUT`设置1–60秒超时。固定官方URL，Bearer不跟随HTTP重定向到其他地址。`.env.example`只是变量说明；程序不自动读取.env。`mcp-config.example.json`只含环境变量占位符，供宿主连接器参考；具体宿主是否支持环境展开需按其文档配置，不要把真实Token写回公开示例。

## 实际验证状态（2026-10-24）

- 官方真实initialize与tools/list成功，发现35个工具，所需8个工具均实际只读调用成功。
- 自动适配整轮22次业务调用、8次试算请求，包含2次无券空购物篮对照（已拒绝），6候选中4个通过25元、700千卡与测试时间假设。
- `data.price`为整数分，试算结果的productList商品编码与数量须等于请求；空篮0元不采纳。已有券与门店券交集仍须整单核价。券有效期按实际tradeDateTime核验，到店前失效不采用。
- `list-nutrition-foods.data`真实返回带字段表头的TOON字符串，现有适配严格解析行数、字段及energyKcal，以完整组成的精确名称匹配求和；未知/冲突不填假热量。自动模式不做餐品别名猜测。
- 自动测试83项通过，涵盖真实发现结构的合成夹具、错误码、复杂套餐、默认特调、空篮、数量不符、有效期、权限和脱敏。本地SDK协议测试另行通过；测试从不读取Owner的真实Token。
- 真实数据原文保存在被Git忽略的private目录、600权限。公开只包含[脱敏验收记录](docs/live-validation.md)与日期明确的[历史报告](docs/live-example.html)。

`tests/fake_mcp_server.py`和`examples/live-recipe.test-double.json`仍仅是本地协议测试双，不能当官方schema使用。演示主页面/主截图为mock；历史真实报告单独标日期且不当实时数据。未使用WorkBuddy，不提交workbuddy.md，不申请虚假联动记录。

## 数据与限制

价格来自本轮calculate-price，拒绝挂牌价作为应付价；金额单位由Agent根据真实结果明确指定。无券对照必须使用相同门店、商品规格和取餐方式；程序比较剥离优惠字段后的请求对象，优惠字段语义仍需Agent核实。价格5分钟新鲜度是本项目策略，不是官方锁价。优惠券有效期若响应提供，应映射真实结果，未来到店仍须重新核价。

门店及餐品名称、餐品编码、热量和券描述有明确来源指针。数字字段的语义、营养与整个候选的对应关系仍由Agent依据真实响应核验；Python能校验结构和来源工具，不能独立理解自然语言券规则。错误或结构变化立即停止，不退回模拟结果冒充实时。`private/audit.json`保存本地调用参数与结果供核验（不含请求头）；默认600权限、Git忽略。不要对外上传该文件。

自动适配的单选套餐不枚举全部搭配。餐品主食/偏好短名单使用名称启发式；复杂配料和过敏原不作保证。名义门店距离不等于步行时间，CLI输入耗时均为调用者确认的假设。券tradeDateTime按麦当劳中国北京时间解释，未知格式不采用。自动模式最多2店6候选，通用配方模式最多3店12候选。无券商品可能不能独立购买：即使HTTP/业务成功，只要productList为空或不匹配，也不是有效对照。
