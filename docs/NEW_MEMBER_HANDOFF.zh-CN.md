# SpireAgent 新成员与 Agent 完整交付指南

适用对象：已收到 GitHub 邀请、已加入 Hub，希望参与采集、数据、模型、工程和运维的新成员，以及受其委托的 Agent。

这是一份入门与任务路由指南，不建立第二套治理、部署或数据契约。操作前以当前仓库规范、代码和 exact runtime evidence 为准。发布日期快照为 2026-09-15；后续版本应重新核对，不把本页的旧 SHA 当永久安装要求。

## 1. 你接手的是什么

唯一开发仓库：<https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project>。仓库名的 `Pefect` 是实际拼写，不要自行改成 `Perfect`。

云端入口：<https://hub.2-fire-2.com/app/>。已有 Hub、TLS、对象存储和备份；新成员接入现有服务，不另建一套云。

系统的主线是：

```text
你自己的 STS2 + 一个 STS2_PLATFORM Mod
  → 本机原始录制
  → Recorder Close
  → 本地工作台：封包、持久上传队列
  → 云端 Hub 验证 / R2 存储 / 回执
  → 按明确规则建立不可变数据集
  → STPD 数据视图、训练、评估
  → 模型产物存储和下载
  → 本地工作台 + Policy Runtime + Connector 进行真实游戏评估
```

采集上传、数据集建立、训练任务、模型运行是不同操作，前一项成功不自动启动后一项。模型文件单独分发；项目源码不是模型权重。

| 组件 | 到哪里找 | 它负责什么 |
|---|---|---|
| 游戏原生接入 | `components/native-foundation`、`components/connector` | STS2 原生事实、公开状态/合法动作和执行接口 |
| 进程与录制 | `components/host-runtime`、`components/annotator` | 游戏生命周期、真人决策及因果证据 |
| 不可变证据 | `components/evidence` | 验证、封包、存储传输与回执 |
| 模型运行边界 | `components/policy-runtime` | 控制器与交付生命周期；不承担模型推理或重建合法性 |
| 一个游戏 Mod | `apps/game-mod`、`apps/ingame-ui` | 安装包、加载身份、游戏内界面 |
| 项目应用 | `python/spireagent` | Hub、本地工作台、统一网页、成员设备、共享存储与调度设施 |
| 研究 | `python/stpd` | 数据投影、模型、训练、评估 |
| 云操作 | `python/deploy` | Hub/worker 配方、预检、备份、恢复 |
| 全项目规范 | 根目录 `AGENTS.md`、`docs/`、`tools/` | 开发、测试、身份、证据和 PR 治理 |

`apps/workbench` 保留诊断 API，不是第二个用户控制台。`python/` 是一个 Python 环境，不是另一个仓库。旧 Platform/STPD 仓库已归档，仅用于历史追溯；新修复、新 PR、发布和问题单都进入新仓库。

### 已经验证到哪里

本页基线发布为 [project/2026-09-15](https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project/releases/tag/project/2026-09-15)：

- 已验收运行代码：`45ef463e3c13cd82db55601c122a292c37aaae2e`；集成 main/develop SHA 另见发布附件 `integration-receipt.json`。
- 本次 macOS 真人录制 580 条 accepted，580 条 proved/canonical，81 条子选择器正确关联；0 真实失败、0 unresolved。72 条 diagnostic 保留。
- 一局自然失败结束，另一局不完整；Close、上传、云端验收及成员下载字节核对通过。
- Linux/Windows 自动测试通过，不等于 Windows/Linux 原生 Mod 安装已真人验证。
- 没有因此宣称所有角色/版本/稀有路径都已验证，也没有模型质量或 GPU 训练资格。当前 compute budget 为 0；没有新的预算授权时不启动 GPU 或收费任务。

详见 [迁移与默认流程](MONOREPO_MIGRATION.md) 和 [真人证据](evidence/MONOREPO_HUMAN_GATE_2026-09-15.md)。历史证据不改名、不补写成新版本证据。

### 今后每天遵守的简单约定

**一个仓库、两个长期分支、一套生产 Hub；电脑和模型使用各自已验收的固定发布。**

| 位置 | 平时怎么用 | 何时更新 |
|---|---|---|
| `develop` | 开发者通过 PR 汇集改动 | 每个已审查任务合并后 |
| `main` | 记录正式集成/发布状态 | 有意发布一批改动时经 release PR 推进 |
| 开发分支 | 一个问题一个临时 branch/worktree | 完成 review 和 CI 后合并；合并检查通过再删除 |
| 本机运行目录 | 一直用同一份已验收源码/工具与私有配置 | 真正需要功能、修复、安全或兼容性更新时，由操作者升级 |
| 云端 Hub | 现有共享服务，运行一个 exact image | 运维安排已验证、可回滚的部署；不自动跟随 main |
| 模型与数据集 | 各自不可变产物，有独立 ID | 新选择/新训练/新评估产生新版本，不覆盖旧产物 |

“代码合并了”“发布包已验收”“云已经部署”“某台电脑已升级”是四个可分别核对的事实。不能用一个“最新版”标签代替它们。main、Hub 和各台电脑的 SHA 不一样可以正常；实际接口、能力、原生身份和数据契约必须兼容。

小团队不需要每个工程师建一套云，不需要一提交就发布，不需要每次软件更新重新注册成员/设备或确认相同用途的授权。工作正常且无安全/正确性/兼容性问题时，可以继续用现有固定发布。定期集中检查依赖、安全、容量和备份；紧急安全问题及时处理。没有“永远不更新、永远不崩溃”的承诺，靠固定版本、预检、备份和可回滚发布控制风险。

游戏更新先检查受影响的原生接入；不默认要求 Hub、模型、全体成员一起升级。但当前 native/queue/schema 门槛失败时必须诊断或适配，不能改 hash 或关掉检查。相同 schema 不自动代表不同游戏版本适合混合训练；不同 Git SHA 也不自动代表不兼容。

完整分支、发布和升级规则只由 [根开发流程](DEVELOPMENT_WORKFLOW.md) 维护；[版本与兼容性](VERSIONING.md) 解释精确身份。其他文档引用它们，不再建平行规范。

## 2. 第一件事：确认你有哪几种权限

你已经被邀请，不需要管理员重复添加。先接受 GitHub 邀请，再用被邀请的邮箱登录 Hub。

| 权限 | 怎么确认 | 不自动获得什么 |
|---|---|---|
| GitHub 协作 | 能访问仓库并向自己的主题分支推送 | Hub 私有数据、生产服务器权限 |
| Hub 成员 | 邮箱验证码登录后能看到自己的账号与授权项目页面 | 管理成员、SSH、云平台凭据 |
| Hub 管理员（如职责确实需要） | 云端出现成员管理等管理员操作 | Unix/sudo、OVH、R2、Modal、GitHub 仓库管理权限 |
| 生产运维授权 | 负责人单独交接个人 SSH 公钥、主机身份和必要的受限云访问 | 随意变更预算、公开秘密或绕过 PR |

“会做所有工作”不等于复制管理员的整套凭据。一般工程、采集、授权数据查看和本地模型操作可用普通成员；管理成员需要 Hub admin；生产维护需要另外交接。缺少哪一项就明确报告哪一项，不索要全部 `.env`。

Hub 默认邀请设置允许注册电脑，额度为 3；实际以该成员记录为准。登录身份由邮箱验证码确认，项目访问由 Hub 唯一成员名单决定。GitHub 登录和 Hub 登录分别完成，不是同一个会话。

“电脑”是一次 Workbench profile 登记，不是硬件指纹。日常一人一台电脑复用一个配置。一个物理电脑确需服务不同账号时，用不同私有配置/状态目录和清楚的设备名；不要复制对方的设备凭据、录制或 outbox。不同 OS 用户能提供更明确的文件隔离。

管理员不用为每次采集建活动，不用每次批准上传，也不用为新成员维护 Cloudflare 邮箱白名单。设备绑定时仍由本人核对配对码并确认。

## 3. 先建立开发环境

以下命令从终端执行，示例采用 macOS/POSIX shell。Windows 开发环境按当前 CI 的 Node/Python/.NET 版本准备；涉及游戏原生安装时先核对该 OS 的发布支持，不照搬 macOS 游戏目录。

一次安装：Git、GitHub CLI (`gh`)、Node 20+、uv、Python 3.11、.NET 9 SDK。开发用 SDK，发布工具运行则按其 `runtimeconfig` 要求；不要依赖另一个 Conda 环境里偶然安装的包。版本变更以当前 CI 和锁文件为准。

```bash
git --version
gh --version
node --version
npm --version
uv --version
dotnet --list-sdks

gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
gh auth status

gh repo clone rsgcsg/STS2-The-Pefect-Defect-Project
cd STS2-The-Pefect-Defect-Project
git fetch origin --prune
git switch develop
git pull --ff-only origin develop
git remote -v
git status --short --branch
```

GitHub 登录用自己的账号，浏览器完成授权，不把 Token 发到聊天或提交到 Git。把 Git 提交姓名和邮箱设置为自己的身份；邮箱应关联自己的 GitHub 账号，或使用 GitHub 提供的隐私邮箱。

从仓库根目录安装、检查：

```bash
npm ci
npm ci --prefix python
npm run setup:python
npm run check
```

`setup:python` 按 `python/uv.lock` 安装开发 extras。采集器有较轻的 `cloud` profile；它不是开发测试环境的替代品。不要遇到缺包就随意改锁文件或全局 pip 安装。

这一步不需要 STS2 游戏文件、生产凭据或 GPU。首次通过意味着本机具备 portable 工程环境，不表示游戏已安装/加载或真人数据已通过。

## 4. 首次安装采集器：固定运行目录，不动开发目录

### 4.1 取得已验收发布与独立运行 checkout

保留开发 clone 用于分支和 PR。另建一个长期存在的运行 worktree，例如在开发 clone 根目录执行：

```bash
git fetch origin --tags
git worktree add --detach ../SpireAgent-runtime project/2026-09-15
git -C ../SpireAgent-runtime rev-parse HEAD
```

本页基线应输出 `45ef463e3c13cd82db55601c122a292c37aaae2e`。将来换发布时使用那个发布的确切 ref，先读升级说明；不是让新电脑永远停在本页版本。

运行 worktree 不用于开发，不 `git pull`，不删除/移动，也不在游戏或上传过程中切换提交。Git worktree 依赖原 clone 的 `.git`；保留这两个目录。不要浅克隆或只用 Source ZIP 代替需要 Git 身份的运行 checkout。

从正式发布下载完整 developer kit、`SHA256SUMS`、`candidate-evidence.json`、`human-qualification.json` 和 `integration-receipt.json`，校验发布来源与哈希后再解压。基线 ZIP 为 `SpireAgent-45ef463-developer-kit.zip`：

```text
SHA256 14b33ceab0dfe637f53bac1f6e50a05f660fb59dd7cdd382ba0fa16adf572aa7
Tool ID 9a293774b0ac4664bd0cb78dedb2ea09e5185b7c653724811c4c7c0b073e0633
```

整个 kit 放在稳定目录。不要只拷贝一个 DLL，不下载别人的游戏文件，也不要使用某个工程师私人的 `.local` 或 project.json。

### 4.2 部署游戏 Mod：这是首次安装中需要工程协助的一段

必须完整执行运行 checkout 中的 [developer kit 安装程序说明](../python/docs/DEVELOPER_KIT_INSTALL.md)，它拥有文件 staging 表和身份校验步骤。本页不复制另一套安装脚本。

顺序为：退出游戏与旧工作台 → 核对发布/game/Mod/tool 身份 → 按 staging 表放置发布二进制 → 核对 tracked 工作区仍干净 → 设置真实 `STS2_GAME_DIR` → 执行 owner lifecycle。

macOS 的 `STS2_GAME_DIR` 指包含 `SlayTheSpire2.app` 的游戏目录，不是 `.app` 本身。基线实际验证游戏为 v0.111.0 / `41cef1ea`；标签一致还不够，必须按安装说明核对程序集 SHA/MVID 及依赖。遇到兼容性拒绝时保留错误，不改 manifest 让它强行匹配。

在固定运行 checkout 根目录，分别执行并保存结果：

```bash
npm ci
npm run game-mod:doctor
npm run game-mod:deploy
npm run game-mod:doctor
npm run game-mod:launch
npm run game-mod:verify-loaded
```

前置 staging/身份校验未完成不能直接执行 deploy。这里安装已发布字节，**不要运行 build 命令覆盖 kit 二进制**。`launch` 只启动程序，不代表可以让 Agent 开始替你玩游戏。

第一次可能需要本人在 STS2 界面启用 Mods 和 `STS2_PLATFORM`，然后完全退出、重新启动并检查加载。不要关闭其他用户需要的 Mod 或修改未知配置来消除错误。

### 4.3 打开工作台、登录、登记本机

选一个本机私有配置绝对路径，以下 `/ABS/PRIVATE/project.json` 是占位符，需替换为这台电脑自己的实际路径。后续所有命令使用同一路径。

在固定运行 checkout 根目录：

```bash
npm run workbench -- --config /ABS/PRIVATE/project.json --hub-url https://hub.2-fire-2.com
```

启动器安装锁定的轻量依赖、在首次运行时创建本机配置，并打开实际 loopback 地址。不要照抄别人的 `127.0.0.1` 端口，也不要为已有配置重新运行 setup。

在 **账号与电脑** 登录被邀请的邮箱，核对电脑名/配对码并在云端批准。账号显示成功和电脑授权成功是两步；已有账号不需要重复邀请。授权完成后，后台设备上传凭据和个人浏览器会话分开保存，登出个人账号不等于撤销后台设备。

### 4.4 登记固定工具和启用录制

在固定运行 checkout 的 `python/` 目录，用同一私有配置执行：

```bash
uv run --locked python -m spireagent.workbench project stop --config /ABS/PRIVATE/project.json
uv run --locked python -m spireagent.workbench project collection-tool --config /ABS/PRIVATE/project.json --tool-directory /ABS/KIT/collection-tool --tool-release-id 9a293774b0ac4664bd0cb78dedb2ea09e5185b7c653724811c4c7c0b073e0633
uv run --locked python -m spireagent.workbench project open --config /ABS/PRIVATE/project.json
```

关闭网页标签不等于停止工作台；登记要求服务停止。`tool-directory` 指整个固定工具目录。其他发布必须换成其独立批准的 Tool ID，不从报错中随便复制一个值去覆盖身份。

工作台 **录制与上传** 页面按顺序完成：

1. 本人阅读日常录制说明，确认真人来源、上传及项目成员共享授权；Agent 不代勾选，不推断同意。
2. **准备本机录制配置**：等待持久准备状态完成。
3. 游戏完全退出后，填写本机安装目录，**绑定本机录制目录**。
4. 冷启动游戏，确认当前原生连接和录制根目录；再 **启用本机上传**。
5. 本人做一段有边界的新录制，按 Recorder **Close**。
6. 在记录详情核对封包、上传、**云端已验收**及对应 receipt；再到云端确认同一记录可见。

正式日常采集不需要另建专题活动。已存在配置/目录冲突时停止该步骤并诊断，不能靠新注册一台“电脑”、删目录或手改 outbox 绕过。

首次安装完成的条件是：本机 doctor、loaded、目录绑定、上传 preflight、真实 Close 和远端回执分别通过。仅“界面能打开”不够。上述真人步骤必须由本人执行；Agent 做准备、读证据和审计。

## 5. 日常怎么用、在哪里看结果

保存固定运行目录和私有配置的启动命令，制成本机快捷方式。日常重新打开同一个工作台即可；目前没有自动安装 OS 开机自启动服务。

| 你要做什么 | 在哪里做 / 怎么判断 |
|---|---|
| 采集 | 工作台运行，游戏内 Recorder 录制，结束记录按 Close；Close 不等于游戏自然结束 |
| 看本机未上传记录 | 本地工作台的 **这台电脑**、**录制与上传** 和记录详情 |
| 看云端收到什么 | 云端或本地授权项目视图的 **采集记录**；核对 exact receipt 和质量结果 |
| 看数量/分类 | **数据统计**；区分上传次数、去重内容、决策数、完整/不完整局 |
| 选择和冻结数据 | **数据集**；预览、确认选择规则，检查包含/排除及去重结果 |
| 下载 | **数据下载**；等待固定文件清单和校验完成 |
| 看训练/模型记录 | **训练与分析**、**模型与评估**；没有记录不代表系统自动训练过 |
| 本地接入模型 | 按 **本机模型**及对应模型/Policy package 文档核对产物和兼容性，显式选择运行模式 |
| 停止后台 | `project stop --config ...`；只关闭浏览器标签不会停止后台 |

网页刷新、退出浏览器、个人会话过期、设备撤销、工作台停止是不同事件。断网时保留本地录制与队列，联网后检查已有任务，不手动重复创建同一上传来“保证成功”。本地原始数据不会在云端成功后自动删除。

云端可在采集电脑关闭时展示已接收数据；它不能看到未上传的本地队列，也不能通过云页面替你绑定本地目录或远程启动游戏。

## 6. 数据、模型、训练：允许做什么，不能混淆什么

一次录制可能有多局，也可能只有局的一部分。完整局、胜负和边界必须来自原生证据；没有终点就是不完整/未知，不补造。重复上传不等于多一局独立数据。

已实现 decision-dataset 路径允许在明确规则下选取有独立证明的成功决策；不要因此修改旧的严格 Full-Run admission 契约。参见 [decision-dataset ADR](../python/docs/adr/0007-fixed-decision-datasets.md) 和 [收口证据](../python/docs/evidence/DECISION_DATASETS_CLOSEOUT_2026-09-15.md)。

建数据集时记录：来源及内容哈希、选择规则、各类包含/排除原因、去重口径、版本/角色/难度分布、完整性和 split。先看预览再冻结；不同版本能否混合取决于数据契约与研究目标，不是“版本号不同一定不能用”，也不是“都是 JSON 就能混”。

失败记录保留用于维护；受影响决策及依赖它的证据不能当成功训练标签。记忆/多步序列遇到缺口要断开，不能把前后成功行硬拼成连续轨迹。同一真实局和重复相关内容不能跨 train/dev/test 泄漏。胜负标签要有自己的 run/terminal 证据。

训练前先读 [FULLRUN_RESEARCH](../python/docs/FULLRUN_RESEARCH.md)、[FULLRUN_TRAINING](../python/docs/FULLRUN_TRAINING.md) 与 [B Pipeline 操作](../python/docs/CLOUD_PIPELINE_B.md)。确认当前入口实际支持的数据契约、模型、预算和 worker；设计文档中的模型不等于都已实现。不要把 decision-dataset 直接塞进不兼容的历史训练入口。

训练输出必须带数据集/输入视图、代码、锁文件、配置、随机种子、checkpoint 和评价协议身份。离线拟合人类与真实游戏能力分开报告。模型真实操作不能混入真人数据；候选动作的内部推演不能改变正式历史/记忆。

本地模型接入先检查模型 manifest、表示、adapter、Reads、候选动作契约和环境支持，再按已授权目标做 Shadow / One-Step / Auto 等模式。下载模型不自动运行它。模型产物可信度、训练资格、GPU 预算和真实游戏操作权限分别确认。

## 7. 任何修复必须从新 branch / PR 开始

这是日常必守规则，适用于人和 Agent，包括“只改一行”、文档、配置模板和运维脚本。

先按顺序读：根 `AGENTS.md` → `README.md` → `docs/memory/CURRENT.md` → `docs/ARCHITECTURE.md` / `docs/COMPONENTS.md` → 相关组件说明和代码/测试。再读 [开发流程](DEVELOPMENT_WORKFLOW.md)、[测试](TESTING.md)；架构、契约、证据、跨层、云/运行时变更必须读 [治理](ENGINEERING_GOVERNANCE.md)。

在开发 clone（不是运行 checkout）先检查是否有未提交工作，不能 reset/stash 掩盖别人的工作。干净时：

```bash
git status --short --branch
git remote -v
git fetch origin --prune
git rev-parse origin/develop
gh pr list --repo rsgcsg/STS2-The-Pefect-Defect-Project
git worktree add -b fix/collector/describe-problem ../SpireAgent-fix origin/develop
cd ../SpireAgent-fix
git rev-parse HEAD
```

将示例分支名改成当前问题；每个任务一个短期分支，每个写入者一个 worktree。记录 exact base SHA。不要复用已合并分支，不直接向 main/develop 提交或推送，不 force push，不在旧仓库修。

按 owning fact 修最先出错的事实：先定位是原生决策、因果归属、投影、传输、身份、UI 还是研究处理；不要为 UI 好看而改写原始 disposition，不在 consumer 建第二套 legality 或因果账本。

必须保持 `H != S`、`CausalRoot != DecisionOccurrence`、execution `S + A(S)`、Commit 与 successor 分离、准确父子/root lineage；不跨 Human effect 借 proof，不用 timer/later frame 把 unknown 补绿。未知执行结果不能自动重试；已明确设计的幂等传输恢复按原 owner 继续。

修改后跑最低忠实回归和组件检查，再跑根 gate：

```bash
npm run check
npm run project:closeout
git diff --check
git diff --stat
git diff
```

`project:closeout` 是影响提示，不会替你更新 BOM/文档或证明测试通过。改变组件源码要核对 component identity/BOM/契约/版本影响。通过现有接口消费，不因为同仓就 import 另一个组件的私有实现。

用明确文件列表提交，不把整目录输出一股脑加入 Git：

```bash
git add <本次已审查的文件>
git commit -m "fix: explain the owning correction"
git push -u origin fix/collector/describe-problem
gh pr create --base develop --draft --title "Describe the actual change" --body-file /ABS/PRIVATE/pr-body.md
```

PR 正文依根 [PR 模板](../.github/PULL_REQUEST_TEMPLATE.md) 写：exact base/head、G0–G6、owner、第一错误事实、改动/非目标、契约及身份、测试/证据、回滚和 non-claims。没有跨仓变更就明确不适用，仍保留相关历史依赖精确 pin。

推送修复后看 **最新 head** 的 CI，不能借上一个提交的绿灯。若 develop 前进，按仓库规则合并最新 base、处理冲突并重验；不为方便改用 force push。自查后请求 reviewer，审查发现同一问题的修复继续在该 PR 内正常提交。

组件源码用正常 merge commit，不能 squash/rebase 改写其 source provenance；纯文档按根规范可以 squash。正常修改先进入 develop。计划发布时从选定 develop 建临时 release 分支，必要时合入 main 来满足最新 base 检查，再 PR 到 main。只在 release/main 产生的稳定性修复要经 PR 同步回 develop；两者树已一致时不用为了 merge-only ancestry 差异开空同步 PR。合并后验证实际 merge-head CI，才删除已合并主题分支；main/develop 是仅有的长期分支，并非禁止工作期间出现临时分支。

### 测试要匹配声明

| 改动 | 还需要什么 |
|---|---|
| 文档/纯 portable 工具（G0） | project/root gate、closeout、diff；不伪造 runtime 验收 |
| 实现/跨层契约（G1/G2） | faithful regression、组件、consumer/contract 和 root gate |
| 游戏原生源码（G3） | exact-game、干净构建和身份；不能把公开 CI 当原生验证 |
| 安装/运行生命周期（G4） | 安装、cold-load、verify-loaded、回滚准备 |
| 真人因果/证据（G5） | 对应原生/runtime gate、有限真人 canary、正式工具审计 |
| 云部署（G6） | 对应预检/隔离集成、部署验收、观察和回滚证据 |

这是索引，具体最大要求以 [TESTING](TESTING.md) / [治理](ENGINEERING_GOVERNANCE.md) 为准。需要 native/runtime/Human 工作时使用仓库相应 Skill。Agent 不代打真人 canary，也不能把口头“完成”替代 exact session 审计。

## 8. 生产维护和发布交接

Hub 成员身份不授权生产维护。接手运维时，负责人另外交接：主机地址/Unix 用户/端口、你的个人公钥授权、可信 host-key 指纹、当前与回滚 source/image/config、真实状态目录、备份回执与恢复资料位置、云平台受限账号和授权预算。秘密通过私有渠道交接，不能写进这份公开指南或问题单。

常规健康日只看云端管理员 System 中容量、备份新鲜度和失败/等待任务。需要诊断或部署时再 SSH；不要求每天跑一套手工备份命令。现有主机操作的唯一来源是 [RUNBOOK](../python/deploy/hub/RUNBOOK.md) 和 [OPERATIONS](../python/deploy/hub/OPERATIONS.md)。不要把 bootstrap/members-bootstrap 当新成员安装步骤，在已有生产数据库上重跑。

日常网页/上传用 HTTPS；SSH 运维是另一条连接。SSH timeout 不是密码错误；Ubuntu KVM 的 `login:` 也不是邮箱验证码入口。没有确认服务器身份就不能跳过 host-key 检查。Rescue/reboot/重置密码按实际中断和授权边界处理，不能见 timeout 就重装。

部署流程：

1. 在新 branch/PR 修改需要的源码/配置模板/运维脚本，完成相关 gate 和 review；秘密仍在服务器外部配置里。
2. 构建并封存一个不可变候选，记录源、锁、Mod/Tool/OCI 身份和部署 profile。Hub 与 GPU worker profile 不可互换。
3. 按 runbook 协调 scheduler/backup writers，验证旧版本离机备份，保留旧 image/config/checkout。现场状态路径以实际部署为准，不盲用示例路径。
4. 部署 exact digest，检查容器、TLS、身份、鉴权拒绝/成功、成员访问、上传/下载和新备份/恢复演练等受影响链路。
5. 改过 checkout 目录时检查所有持久 bind mount 和 systemd 引用。合仓曾发现 TLS 仍挂旧 Caddyfile：当前能访问不代表容器重启能恢复。修正后必须真实重新创建相关服务并验证。
6. 需要真人门槛时，先完成能自动完成的检查，再给出有限步骤、预期证据与回滚；本人执行后 Agent 审计。
7. 按治理集成和发布，发布同一已验证字节。文档 merge SHA 不自动成为运行程序 SHA，不因普通合并重编一个未测包。

普通代码修复不能靠 SSH 直接改运行中的源码作为最终修复。紧急止损可在明确授权下暂停/撤销/回滚，但要保留操作记录，并以新分支/PR 补齐根因修复和回归。不能用紧急操作代替永久可审查修复。

恢复备份先放新目录并保持 paused，核对撤销权限和未知外部任务；不要覆盖正在使用的数据库，也不要仅为代码回滚恢复旧 DB。不要 `docker system prune --volumes` 或删原始数据来临时腾空间。维护脚本、容量预警和清理边界按 owner 执行。

## 9. 遇到问题，先留下什么、找哪里

| 现象 | 第一轮判断与 owner | 不要做 |
|---|---|---|
| GitHub 无法 push | 是否接受邀请、当前账号、origin、主题分支；仓库权限 | 推 main、借别人 Token、force push |
| Hub 登录被拒 | 邮箱是否正好匹配、成员是否停用、浏览器会话；Hub membership | 绕过 Hub、反复修改 Cloudflare 白名单 |
| 注册电脑失败 | 是否允许登记/额度已满/已有配置；account/device owner | 复制别人的 profile 或删旧登记掩盖问题 |
| 页面正常但录制未准备 | 工具是否完整、准备/绑定/loaded 各阶段；Workbench/Mod | 用手改 JSON 跳过准备门槛 |
| 更新游戏后 loaded 不通过 | 实际 game/Mod/依赖身份和错误；Host/Game Mod | 修改 hash、伪称兼容或关闭校验 |
| Close 后待上传 | 本机服务、队列状态、网络/鉴权、对应 receipt；Evidence/Hub | 重新录制/重复上传当作修复、删除 outbox |
| 已上传但质量有失败 | 原始 disposition、canonical、lineage、run 边界；Annotator/研究分别判断 | 将 diagnostic 算真实失败或把失败改 valid |
| 数据集少于上传数量 | 权限、去重、选择规则和排除原因；dataset owner | 把每次上传都算独立局 |
| 模型不能运行 | 模型产物、adapter、表示/Reads/动作契约和环境；对应 owner | 编造动作、扩大模型支持声明 |
| 云服务异常/磁盘满 | System、health、blocks/inodes、容器和备份；运维 | 无差别删数据/卷、无备份重建 |
| SSH timeout / KVM login | 按 OPERATIONS 区分网络、主机身份、认证和救援 | 公开 SSH 日志/私钥、把邮箱 OTP 当 Unix 密码 |

在[新仓库 Issues](https://github.com/rsgcsg/STS2-The-Pefect-Defect-Project/issues)报告或更新同一根因的现有问题。当前并不承诺所有故障都会自动通知或自动建 issue；要核对采集质量和运维事件两边。公开记录只放脱敏摘要，原始人类数据和凭据留在授权私有存储。

可复制的问题报告：

```text
标题：具体触发 + 实际错误
发生时间（含时区）/ OS / 任务阶段：
预期结果 / 实际结果 / 最短复现：
代码 repo + SHA / branch / PR：
发布 tag、Tool ID；相关 game/Mod SHA/MVID 或 OCI digest：
session / run / decision / receipt / dataset / job ID（按相关性）：
真实失败、unresolved、diagnostic 分开计数；不知道写 unknown：
脱敏错误原因 / 日志片段 / 可安全共享的截图：
私有证据位置与有权访问的人（公开帖不暴露私有路径或临时签名 URL）：
影响范围 / 已做操作 / 是否仍在复现：
初步 owner、待验证假设、当前止损及回滚：
```

日志先检查是否包含 Cookie、Authorization、验证码、Token、R2 签名 URL、完整环境变量、个人路径或原始数据。不要把 `cat *.env`、完整 docker inspect 或原始 bundle 贴到公开 issue。凭据泄露先按授权撤销/轮换并保留事件记录，不能靠删帖就声称解决。

修复按第 7 节走新分支/PR；报告、修复提交、回归、发布和复测结果互相链接。原失败证据保持失败，新报告说明哪个版本修了什么，不能回写历史让统计变绿。

## 10. 可以直接交给 Agent 的任务说明

复制下面的说明，补充具体任务和已授权范围，不包含秘密：

```text
唯一仓库：rsgcsg/STS2-The-Pefect-Defect-Project。
我的任务：<具体目标>；非目标：<不做什么>。
已有 GitHub / Hub 权限：<实际具备的权限>。
允许的本地修改、部署、云操作和预算：<具体范围；没有就写没有>。
当前运行 checkout / 私有 config 位置：<仅在私有会话提供路径，不粘贴凭据>。
已观察的版本、问题 ID 与证据：<脱敏资料>。

先核对 cwd/origin/status/现有 PR，按根 AGENTS.md 的顺序读规范和当前 owner 源码。
从最新 origin/develop 创建新的短期 branch/worktree；不在 main/develop、旧仓库或运行 checkout 修复。
只读任务不改文件；修复任务先定位第一错误事实与 owning layer，不降低 evidence/identity 标准。
完成实现、最低忠实回归、组件/root 检查、closeout、diff review 和 PR；更高风险按 G0-G6 补 gate。
不得提交 secrets、原始 Human 数据、游戏文件、模型权重或 .local；不得 force push 或绕过 CI。
未经本任务授权不启动 GPU/收费任务、真人 gameplay 或生产变更。
明确区分本地测试、CI、构建、安装、加载、Human、训练与科学结论。
只在真实缺权限、外部人工登录/验证码、真人游戏步骤或超出授权的操作处停下，给最短步骤。
最后报告 exact base/head/PR、变更原因、测试与证据、剩余问题、回滚、下一步。
不要在工作结束后把仍有未合并工作的分支删掉。
当前仓库和运行时证据高于这份交付说明。
```

若负责人只要求提交待审 PR，做到可审查交付即可，不擅自 merge/deploy；若已明确授权整个发布，则完成对应治理流程，不重复索要已授予的权限。缺 secret 时先确认它是否已存在于批准的本地私有配置，不让人反复粘贴。

## 11. 第一次接手的完成标准

- [ ] 能说清 Mod、Workbench、Hub、STPD 各自职责，并确认只使用新仓库。
- [ ] 接受 GitHub 邀请，自己的账号/提交身份正确；Hub 登录与所需权限已核对。
- [ ] 开发环境根 gate 通过；运行 checkout 与开发 worktree 隔离。
- [ ] 按已支持发布完成 Mod/Tool 安装、身份与 cold-load 验证；不支持的平台仍明确未通过。
- [ ] 自己的设备、私有配置、授权和录制根目录正确；本人新录制 Close 后取得云端回执。
- [ ] 能查记录质量、数据统计/选择/下载；知道上传成功不等于训练完成。
- [ ] 做过一次正常 branch → PR → review/CI 流程；没有直接修改集成分支。
- [ ] 若接管生产，另有个人受限访问、备份/恢复与回滚交接；没有则明确尚未接管。
- [ ] 知道去哪里报故障，能提交脱敏且可追溯的问题，清楚哪些必须由真人完成。

本轮仅更新指南/规范，不要求重建 Mod、重启 Hub、升级已在工作的采集器或重复真人测试。以后是否需要这些步骤，由实际改动和声明的风险决定。

后续维护本指南时也走新 PR。保持它作为入口和解释；安装细节由 developer-kit 文档、生产操作由 runbook、研究准入由 STPD 契约拥有，不继续复制出第二套实现。

**当前仓库源码、治理和 exact runtime evidence 始终高于本交付说明。**

## 日常开发和发布的简化规则

- 普通工作：从最新 develop 开独立分支，修复、相关回归、按影响检查、PR、合 develop；除非任务要求上线，到这里就完成。
- 正式交付：负责人选一批可发布改动，经 release PR 合 main；发布清单指定实际产物。main 有文档更新，不代表全员重装。
- 检查入口：`npm run check:plan -- --base origin/develop --run`。普通说明文档可走 Node 轻检查；源码、契约、治理、未知影响仍走全套。原生/Human 等更高证据要求另外保留。
- 安装入口：按[开发者包安装指南](../python/docs/DEVELOPER_KIT_INSTALL.md)使用已批准 ZIP 与其一个校验值，工具准备固定目录、锁定环境和已发布二进制；不再手抄全部组件 hash。
- 本地工作台“系统”页区分本机和 Hub 来源，链接正式发布说明。不同 SHA 不自动阻止连接；未知格式、过期观测和真实错误必须显示。
- 云端普通更新：按 [RUNBOOK](../python/deploy/hub/RUNBOOK.md) 的 rollout 计划/应用入口，只更新受影响 Hub；数据库或配置变化走明确迁移流程。
- 不改旧记录、不清 pending 队列、不共享私人凭据；所有 bug、架构或跨组件修复仍开新分支和 PR。问题报告附原始 session/upload/job ID、来源、时间、期望与实际、脱敏错误，不贴 Token。

规范分别由 DEVELOPMENT_WORKFLOW、TESTING、VERSIONING 和 owning RUNBOOK 维护；
本指南是入口，不再复制另一套发布命令或版本表。普通成员不需要 SSH 管服务器，
工程师也不需要为每次提交维护一次生产部署。
