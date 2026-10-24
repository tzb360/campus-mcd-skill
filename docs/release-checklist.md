# 发布及报名交接（尚未执行）

预定仓库：`https://github.com/tzb360/campus-mcd-skill`。这是拟用地址，尚未创建或发布。**未经项目Owner明确授权，不创建Public仓库、不push、不提交报名Issue。**

## 发布前必需

- 本人确认满足[官方活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)所列身份、年龄/监护人同意与账号条件，并同意原样参赛声明。
- 已完成真实discover及8工具只读联调，最终自动规划22调用/8次试算；原始审计保留private，公开只用脱敏历史样例。发布前重新检查源码与文档，不上传私有目录。
- 核查CONTEST_DECLARATION.md仍与官方文件逐字节一致，README中的验证结论为真实状态，仓库不含凭据和个人数据。
- 公开前读取当前榜单和规则，门槛会变。当前已核验为2026-10-24 21:00:54的51 Star。

## 已授权后可直接使用的命令

当前本机未安装`gh`，可安装官方GitHub CLI并使用`gh auth login`授权；不要把GitHub凭据放进项目。先完成上面的真实联调和文档更新，再运行：

```bash
cd /path/to/campus-mcd-skill
python -m pytest -q
ruff check src tests scripts
python -m build
# 若尚未提交本地更改，先检查并提交。
git status --short
gh repo create tzb360/campus-mcd-skill --public --source=. --remote=origin --push --description '下课只有40分钟？把预算、返课时间和官方MCP整单试算一起算。Python Agent Skill，含隐私报告与离线演示。'
gh issue create --repo M-China/mcd-developer-innovation-challenge --title '【参赛申请】下课开麦 / CampusMcD' --body-file docs/submission-issue.txt
```

如仓库名或Owner发生变化，先修改submission-issue.txt的裸URL。不能把该草稿中的预定地址当作已存在地址。也可手工在[GitHub新建仓库](https://github.com/new)后上传源码，再前往[官方新建Issue](https://github.com/M-China/mcd-developer-innovation-challenge/issues/new)粘贴正文；必须保持字段名与内容同一行。

## 提交后核验

```bash
gh issue view ISSUE_NUMBER --repo M-China/mcd-developer-innovation-challenge --comments
```

记录真实Issue URL及官方机器人/维护者回复。失败则按官方原因修正，依据主页说明重新报名；未回复就是待审核，不是成功。收到成功通知也不等于最终获奖审核通过。

可选GitHub Pages：Settings → Pages → Deploy from a branch → main /docs。当前网页含mock标记且完全静态，无Token。页面上线须在已获公开发布授权后操作，不需要新建云服务。

## 临近截止与领奖

报名截止北京时间10月25日23:59，最终排名以10月26日00:00采集为准；预留审核和修正时间，不能保证主办方处理速度。只做真实分享、体验与反馈，不刷Star。最终获奖审核通过后留意账号邮箱/OAuth通知，11月14日前从官方链路提供领奖信息；不在公开Issue提供手机号、收货地址或会员信息。
