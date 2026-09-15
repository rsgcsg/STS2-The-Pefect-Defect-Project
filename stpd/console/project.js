"use strict";

// Presentation only. Hub owns membership/data; the local service owns files and processes.
window.SpireProject = (() => {
  const local = document.body.dataset.mode === "local";
  const hex = (value, length = 64) =>
    typeof value === "string" &&
    new RegExp(`^[a-f0-9]{${length}}$`).test(value);
  const selectionId = (value) =>
    typeof value === "string" && /^[a-z0-9-]{1,80}$/.test(value);
  const supported = new Set([
    "members",
    "statistics",
    "downloads",
    "research",
    "local-models",
    "campaigns",
    "collection-overview",
    "datasets",
    "games",
  ]);
  let current = null;
  let account = null;
  let offsets = new Map();
  let drafts = new Map();
  let selected = new Set();
  let artifacts = new Map();
  let exportId = null;
  let readiness = new Map();
  const pending = new Set();
  const labels = {
    invited: "待首次登录",
    active: "已启用",
    disabled: "已停用",
    member: "成员",
    admin: "管理员",
    accepted: "游戏接受",
    proved: "因果后继已证明",
    canonical: "已录入决策",
    real_failures: "真实录制失败",
    cancelled: "正常取消",
    aborted: "中断",
    diagnostics: "诊断",
    unsupported: "不在记录范围",
    unresolved: "后继未解决",
    invalidations: "显式 invalidation",
    accepted_children: "接受的子决策",
    canonical_children: "已录入子决策",
    native_starts: "观测到原生开局",
    native_ends: "观测到原生终局",
    assigned_run_count: "已分配 run 的数量",
    recorder_pauses: "记录器暂停",
    device: "电脑",
    status: "接收状态",
    campaign: "采集活动",
    format: "记录格式",
    disposition: "记录 disposition",
    action_family: "动作类别",
    surface: "交互界面",
    decision_kind: "决策类型",
    character: "角色",
    difficulty: "难度",
    game_version: "游戏版本",
    evidence: "证据",
    dataset: "数据集",
    training_input: "训练输入",
    experiment: "实验配置",
    run: "训练运行",
    run_result: "训练结果",
    checkpoint: "检查点",
    model: "模型",
    offline_evaluation: "离线评估",
    live_evaluation: "游戏评估",
    performance: "性能",
    analysis: "分析",
    idle: "尚未加载",
    loading: "正在加载",
    loaded: "已加载",
    stopped: "已停止",
    failed: "操作失败",
    runtime_exited: "进程已退出",
    recovery_required: "需要确认上一进程",
    command_unknown: "命令结果未知",
    downloading: "正在下载并校验",
    verified: "文件校验完成",
    quarantined: "已接收，隔离待审",
    pending: "服务处理中",
    completed: "操作已完成",
    unknown: "结果未知",
    ready_to_load: "可请求加载",
    blocked: "条件未满足",
    human: "人类控制",
    shadow: "Shadow 只评分",
    one_step: "执行一个决策",
    auto: "自动决策",
  };
  const show = (value) =>
    labels[value] ||
    (value === null || value === undefined ? "未知" : String(value));
  const count = (value) =>
    typeof value === "number" && Number.isFinite(value)
      ? value.toLocaleString("zh-CN")
      : "未知";
  const when = (value) => {
    if (value === null || value === undefined || value === "")
      return "未提供观测时间";
    const date = new Date(typeof value === "number" ? value * 1000 : value);
    return Number.isFinite(date.getTime())
      ? date.toLocaleString("zh-CN")
      : "未提供观测时间";
  };
  const bytes = (value) => {
    if (!Number.isFinite(value) || value < 0) return "大小未知";
    if (value < 1024) return `${value} B`;
    const unit = Math.min(3, Math.floor(Math.log(value) / Math.log(1024)));
    return `${(value / 1024 ** unit).toLocaleString("zh-CN", { maximumFractionDigits: 1 })} ${["B", "KiB", "MiB", "GiB"][unit]}`;
  };
  const el = (tag, text, cls) => {
    const item = document.createElement(tag);
    if (text !== undefined && text !== null) item.textContent = String(text);
    if (cls) item.className = cls;
    return item;
  };
  const panel = (title, description) => {
    const box = el("section", null, "panel project-panel");
    if (title) box.append(el("h2", title));
    if (description) box.append(el("p", description, "muted"));
    return box;
  };
  const empty = (title, description) => {
    const box = el("div", null, "empty-state");
    box.append(el("strong", title), el("p", description));
    return box;
  };
  const badge = (text, kind = "neutral") => el("span", text, `badge ${kind}`);
  const link = (label, target) => {
    const item = el("a", label, "button");
    item.href = target;
    if (target.startsWith("?view=")) {
      item.onclick = (event) => {
        if (
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey ||
          !window.SpireProject.navigate
        )
          return;
        const query = new URLSearchParams(target);
        event.preventDefault();
        window.SpireProject.navigate(query.get("view"), query.get("id"));
      };
    }
    return item;
  };
  const route = (view, id) =>
    `?view=${encodeURIComponent(view)}${id ? `&id=${encodeURIComponent(id)}` : ""}`;
  const project = (path) => {
    if (window.SpireIdentity?.api && !window.SpireIdentity.isLocal()) {
      const split = path.indexOf("?");
      return window.SpireIdentity.api(
        split < 0 ? path : path.slice(0, split),
        split < 0 ? "" : path.slice(split),
      );
    }
    return (local ? "/api/project/" : "/app/api/") + path;
  };
  const member = (path) => (local ? "/api/member/" : "/app/api/member/") + path;
  const cloudLink = (view) => {
    try {
      const url = new URL(document.body.dataset.cloudUrl);
      if (
        url.protocol !== "https:" ||
        url.username ||
        url.password ||
        !["", "/"].includes(url.pathname) ||
        url.search ||
        url.hash
      )
        return null;
      return url.origin + "/app/" + route(view);
    } catch {
      return null;
    }
  };
  const scope = () => window.SpireIdentity?.context?.() || "";
  const live = (ctx) => current?.key === ctx.key && scope() === ctx.scope;
  const signedIn = (ctx) =>
    Boolean(ctx.identity?.principal) &&
    (!local || ctx.identity.status === "signed_in");
  const note = (ctx, text, kind = "good") => {
    if (!live(ctx)) return;
    const target = document.getElementById("notice");
    const message = el("div", text, `banner ${kind}`);
    message.setAttribute("role", "status");
    target.replaceChildren(message);
  };
  const failure = (error) => {
    const known = {
      authentication_required: "当前账号已过期或无权访问，请重新登录项目账号。",
      last_admin_required:
        "必须保留至少一位已激活的管理员。先让另一位管理员完成首次登录。",
      member_already_exists: "此邮箱已在成员列表中；请修改现有成员。",
      collection_not_shared: "这份记录尚未授权项目共享，不能下载原始文件。",
      source_sharing_not_established: "数据集引用的原始数据尚未建立共享授权。",
      explicit_campaign_consent_required:
        "请分别确认真人来源、上传授权和项目成员共享。",
      owned_active_device_required:
        "只能为当前账号拥有且仍有效的电脑登记活动。",
      runtime_command_unknown:
        "命令可能仍在执行。请查看当前状态；不要重复命令，可交还人类或停止。",
      previous_operation_requires_recovery:
        "上一操作结果未确认，请先交还人类或停止。",
      model_readiness_blocked: "模型加载条件未满足，请查看逐项兼容性检查。",
      request_unknown: "请求结果尚未确认，请先刷新状态。不会自动重发操作。",
      request_unavailable: "暂时无法读取服务，请刷新重试。",
      absolute_game_directory_required: "请填写这台电脑上的游戏安装目录完整路径。",
      default_collection_fields_required: "请填写名称、录制说明和授权说明。",
    };
    return (
      known[error?.message] ||
      (/^[a-z0-9_:.\/-]{1,120}$/.test(error?.message || "")
        ? `服务未完成请求（${error.message}）。`
        : "服务暂时不可用，请刷新状态。")
    );
  };
  async function request(ctx, path, body) {
    if (!live(ctx)) throw new Error("context_changed");
    const mutation = body !== undefined;
    const payload =
      mutation && !local
        ? { ...body, csrf_token: ctx.identity?.csrf_token || "" }
        : body;
    let response;
    try {
      response = await fetch(path, {
        method: mutation ? "POST" : "GET",
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(mutation ? 25000 : 15000),
        headers: mutation
          ? {
              "Content-Type": "application/json",
              "X-CSRF-Token": ctx.identity?.csrf_token || "",
            }
          : {},
        body: mutation ? JSON.stringify(payload) : undefined,
      });
    } catch {
      throw new Error(mutation ? "request_unknown" : "request_unavailable");
    }
    let value;
    try {
      value = await response.json();
    } catch {
      throw new Error(mutation ? "request_unknown" : "request_unavailable");
    }
    if (response.status === 401 || response.status === 403)
      throw new Error("authentication_required");
    if (!response.ok || value?.error)
      throw new Error(value?.error || "request_unavailable");
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error("request_unavailable");
    return value;
  }
  const authNotice = (ctx) => {
    const box = panel(
      "登录后查看项目",
      "登录状态与电脑上传授权分开管理。未登录不会删除本地记录。",
    );
    if (
      ctx.identity?.status === "unavailable" ||
      ctx.identity?.status === "reconnect_required"
    )
      box.append(el("p", "暂未取得可用账号状态，请重新连接。"));
    box.append(link("账号与电脑", local ? route("devices") : "/app/"));
    return box;
  };
  function command(ctx, name, label, operation, options = {}) {
    const button = el(
      "button",
      label,
      `button ${options.primary ? "primary" : ""} ${options.danger ? "danger" : ""}`,
    );
    button.type = "button";
    button.dataset.action = name;
    const key = `${ctx.account}:${name}`;
    button.disabled = Boolean(options.disabled) || pending.has(key);
    if (options.title) button.title = options.title;
    button.onclick = async () => {
      if (!live(ctx) || button.disabled || pending.has(key)) return;
      pending.add(key);
      button.disabled = true;
      try {
        await operation();
      } catch (error) {
        if (error.message !== "context_changed")
          note(ctx, failure(error), "error");
      } finally {
        pending.delete(key);
        button.disabled = Boolean(options.disabled);
      }
    };
    return button;
  }
  async function reload(ctx) {
    if (live(ctx)) await window.SpireProject.reload();
  }
  function fields(rows) {
    const list = el("dl", null, "fact-list");
    for (const [label, value] of rows) {
      const row = el("div", null, "fact-row");
      row.append(el("dt", label), el("dd", value ?? "未知"));
      list.append(row);
    }
    return list;
  }
  function technical(value, title = "查看精确身份与元数据") {
    const detail = el("details", null, "technical");
    detail.append(
      el("summary", title),
      el("pre", JSON.stringify(value, null, 2)),
    );
    return detail;
  }
  function input(form, label, name, value = "", type = "text") {
    const field = el(
      "label",
      null,
      type === "checkbox" ? "project-check" : "form-field",
    );
    const control = el("input");
    control.name = name;
    control.type = type;
    if (type === "checkbox") control.checked = value === true;
    else control.value = String(value);
    field.append(control, el("span", label));
    if (type !== "checkbox") field.replaceChildren(el("span", label), control);
    form.append(field);
    return control;
  }
  function select(form, label, name, options, value) {
    const field = el("label", null, "form-field"),
      control = el("select");
    control.name = name;
    for (const [key, title] of options) {
      const option = el("option", title);
      option.value = key;
      control.append(option);
    }
    control.value = value;
    field.append(el("span", label), control);
    form.append(field);
    return control;
  }
  function table(headers, rows) {
    const wrap = el("div", null, "table-wrap"),
      grid = el("table");
    const head = el("thead"),
      heading = el("tr"),
      body = el("tbody");
    headers.forEach((title) => heading.append(el("th", title)));
    head.append(heading);
    rows.forEach((values) => {
      const row = el("tr");
      values.forEach((value) => {
        const cell = el("td");
        if (value && typeof value === "object" && value.tagName !== undefined)
          cell.append(value);
        else if (value && typeof value === "object" && value.tag)
          cell.append(value);
        else cell.textContent = String(value ?? "未知");
        row.append(cell);
      });
      body.append(row);
    });
    grid.append(head, body);
    wrap.append(grid);
    return wrap;
  }
  function pager(ctx, key, data, limit = 25) {
    const offset = offsets.get(key) || 0,
      box = el("div", null, "pagination");
    box.append(
      el(
        "span",
        `共 ${count(data.total)} 项 · 当前第 ${Math.floor(offset / limit) + 1} 页`,
      ),
    );
    const actions = el("div", null, "pagination-actions");
    for (const [direction, label, disabled] of [
      [-1, "上一页", offset === 0],
      [
        1,
        "下一页",
        !(typeof data.total === "number" && offset + limit < data.total),
      ],
    ]) {
      actions.append(
        command(
          ctx,
          `${key}-page-${direction}`,
          label,
          async () => {
            offsets.set(key, offset + direction * limit);
            await reload(ctx);
          },
          { disabled },
        ),
      );
    }
    box.append(actions);
    return box;
  }
  function metric(label, value, explanation, kind = "") {
    const card = el("section", null, `metric ${kind}`);
    card.append(
      el("div", label, "metric-label"),
      el("div", count(value), "metric-value"),
      el("div", explanation, "metric-note"),
    );
    return card;
  }
  function metricCoverage(value) {
    return value
      ? `已知 ${count(value.known)} 份上传 · 未知 ${count(value.unknown)} 份${value.partial ? " · 部分汇总" : ""}`
      : "尚无此项摘要";
  }
  function facetPanel(title, facet) {
    const box = panel(title);
    if (!facet || facet.availability !== "available")
      box.append(el("p", "当前没有可用分类，未知不会归入其他类别。", "muted"));
    if (facet) {
      box.append(
        el(
          "p",
          `已知 ${count(facet.known)} · 未知 ${count(facet.unknown)}`,
          "small muted",
        ),
      );
      if ((facet.items || []).length)
        box.append(
          table(
            ["类别", "数量"],
            facet.items.map((item) => [show(item.value), count(item.count)]),
          ),
        );
      if (facet.truncated)
        box.append(
          el("p", "仅展示数量最多的 100 类，列表已截断。", "small muted"),
        );
    }
    return box;
  }
  function profilePanel(title, profile, unit) {
    const box = panel(title, unit);
    if (!profile) {
      box.append(
        empty(
          "尚未建立画像",
          "管理员可以显式刷新选定来源；打开此页面不会处理原始数据。",
        ),
      );
      return box;
    }
    box.append(
      fields([
        ["来源总数", count(profile.sources)],
        [
          "可用画像 / 缺失画像",
          `${count(profile.profiles_available)} / ${count(profile.profiles_missing)}`,
        ],
        ["画像中的记录次数", count(profile.records)],
      ]),
    );
    if (profile.partial || profile.availability !== "available")
      box.append(
        el(
          "p",
          "画像覆盖不完整。以下已知分类只代表已建立画像的来源。",
          "banner",
        ),
      );
    const facets = el("div", null, "project-facets");
    for (const [key, value] of Object.entries(profile.facets || {}))
      facets.append(facetPanel(show(key), value));
    box.append(facets);
    return box;
  }
  async function statistics(ctx) {
    const data = await request(ctx, project("statistics"));
    if (data.schema !== "stpd/project-statistics-v1")
      throw new Error("unsupported_statistics_schema");
    const box = el("div", null, "project-page");
    box.dataset.observedAt = data.observed_at || "";
    const metrics = data.metrics || {},
      cards = el("div", null, "metrics");
    cards.append(
      metric("接收记录次数", data.uploads, "单位为上传记录，不是完整游戏局数"),
      metric(
        "不同内容身份",
        data.unique_content_ids,
        `重复内容上传 ${count(data.duplicate_content_uploads)} 次`,
      ),
      metric(
        "已录入决策",
        metrics.canonical?.value,
        metricCoverage(metrics.canonical),
        "good",
      ),
      metric(
        "真实录制失败",
        metrics.real_failures?.value,
        metricCoverage(metrics.real_failures),
        "danger",
      ),
    );
    box.append(cards);
    const quality = panel(
      "记录质量与原生边界",
      "各项来自 Platform 摘要。不同上传中的计数相加，不代表已跨来源去重。",
    );
    quality.append(
      table(
        ["指标", "已知数量", "摘要覆盖"],
        Object.entries(metrics).map(([key, value]) => [
          show(key),
          count(value.value),
          metricCoverage(value),
        ]),
      ),
      el(
        "p",
        "原生开局与终局数量不能单独证明 uninterrupted Full Run；已分配 run 的数量也不是完整局数。",
        "small muted",
      ),
    );
    box.append(quality);
    const uploads = panel("上传记录分类", "这里每一项以上传记录次数为单位。"),
      facets = el("div", null, "project-facets");
    for (const key of ["device", "status", "campaign", "format", "disposition"])
      if (data.facets?.[key])
        facets.append(facetPanel(show(key), data.facets[key]));
    uploads.append(facets);
    box.append(
      uploads,
      profilePanel(
        "已接收数据的决策画像",
        data.collection_profiles,
        "单位为投影后的 canonical 记录出现次数；缺失画像不会算零，不声称 Dataset 已准入。",
      ),
      profilePanel(
        "数据集画像",
        data.dataset_profiles,
        "单位为已索引数据集中的记录出现次数；同一记录进入多个数据集可重复计数。",
      ),
    );
    const catalog = panel(
      "研究产物目录",
      "这是已发布或显式刷新的索引，不是云存储桶的完整盘点。",
    );
    const entries = Object.entries(data.artifacts?.counts || {});
    if (entries.length)
      catalog.append(
        table(
          ["类型", "已索引身份数"],
          entries.map(([key, value]) => [show(key), count(value)]),
        ),
      );
    else
      catalog.append(
        empty(
          "尚无已索引研究产物",
          "数据接收、Dataset 构建、训练与模型发布是不同步骤。",
        ),
      );
    catalog.append(link("查看训练、评估和分析", route("research")));
    box.append(catalog);
    box.append(
      el(
        "p",
        `服务观测：${when(data.observed_at)}。模型质量与训练许可需各自证据。`,
        "small muted",
      ),
    );
    return box;
  }
  function memberEditor(ctx, item) {
    const key = item?.member_id || "invite",
      original = item || {
        email: "",
        role: "member",
        device_quota: 3,
        enroll_devices: true,
      };
    const draft = drafts.get(`member:${key}`) || original;
    const form = el("div", null, "project-form");
    form.dataset.projectEditor = "member";
    const email = item
      ? null
      : input(form, "邀请邮箱", "email", draft.email, "email");
    const role = select(
      form,
      "角色",
      "role",
      [
        ["member", "成员"],
        ["admin", "管理员"],
      ],
      draft.role,
    );
    const quota = input(
      form,
      "有效电脑额度",
      "device_quota",
      draft.device_quota,
      "number",
    );
    quota.min = "0";
    quota.max = "128";
    quota.step = "1";
    const enroll = input(
      form,
      "允许自行绑定新电脑",
      "enroll_devices",
      draft.enroll_devices,
      "checkbox",
    );
    const read = () => ({
      ...(email ? { email: email.value.trim() } : {}),
      role: role.value,
      device_quota: Number(quota.value),
      enroll_devices: enroll.checked,
    });
    for (const control of [email, role, quota, enroll].filter(Boolean))
      control.oninput = () => drafts.set(`member:${key}`, read());
    form.append(
      command(
        ctx,
        `member-save-${key}`,
        item ? "保存权限设置" : "添加成员",
        async () => {
          const value = read();
          if (email && !/^[^\s@]+@[^\s@]+$/.test(value.email))
            throw new Error("invalid_member_email");
          if (
            !quota.value ||
            !Number.isInteger(value.device_quota) ||
            value.device_quota < 0 ||
            value.device_quota > 128
          )
            throw new Error("invalid_member_quota");
          if (
            value.role === "admin" &&
            original.role !== "admin" &&
            !window.confirm(
              "此账号将能管理成员、电脑与采集活动。确认授予管理员权限？",
            )
          )
            return;
          await request(
            ctx,
            "/app/api/admin/members" + (item ? `/${key}` : ""),
            value,
          );
          if (!live(ctx)) return;
          drafts.delete(`member:${key}`);
          note(
            ctx,
            item
              ? "成员权限已保存。"
              : "成员已添加。请把项目入口发给对方；系统未自动发送邀请邮件。",
          );
          await reload(ctx);
        },
        { primary: !item },
      ),
    );
    return form;
  }
  async function admin(ctx) {
    const box = panel(
      "成员与访问管理",
      "停用会撤销个人会话与该成员拥有的电脑授权，历史数据保留。至少留一位已激活管理员。",
    );
    if (ctx.identity.principal.role !== "admin") {
      box.append(
        empty(
          "当前是项目成员",
          "成员可以查看共享数据、登记自己的电脑和使用研究产物。管理账号由管理员负责。",
        ),
      );
      return box;
    }
    if (local) {
      box.append(
        el(
          "p",
          "管理操作需要云端浏览器的有效登录。工作台个人会话只用于项目读取。",
        ),
      );
      const target = cloudLink("members");
      if (target) box.append(link("打开云端成员管理 ↗", target));
      return box;
    }
    const data = await request(
      ctx,
      `/app/api/admin/members?limit=25&offset=${offsets.get("members") || 0}`,
    );
    const invitation = panel(
      "邀请成员",
      "首次登录时激活邀请，默认可绑定 3 台有效电脑。两种角色均可读取共享项目数据。",
    );
    invitation.append(memberEditor(ctx));
    box.append(invitation);
    for (const item of data.items || []) {
      if (!hex(item.member_id, 32)) continue;
      const row = panel(
        item.email,
        `${show(item.role)} · ${show(item.status)}`,
      );
      row.append(
        fields([
          [
            "当前有效 / 历史绑定电脑",
            `${count(item.active_device_count)} / ${count(item.owned_device_count)}`,
          ],
          ["最近权限变化", when(item.updated_at)],
        ]),
        memberEditor(ctx, item),
      );
      const actions = el("div", null, "project-actions");
      actions.append(
        command(
          ctx,
          `member-status-${item.member_id}`,
          item.status === "disabled" ? "恢复成员访问" : "停用成员及电脑",
          async () => {
            const disable = item.status !== "disabled";
            if (
              !window.confirm(
                disable
                  ? `停用 ${item.email}，撤销其工作台会话与电脑上传授权？历史数据保留。`
                  : `恢复 ${item.email} 的成员访问？已撤销的电脑凭据不会自动恢复。`,
              )
            )
              return;
            await request(ctx, `/app/api/admin/members/${item.member_id}`, {
              status: disable ? "disabled" : "active",
            });
            note(
              ctx,
              disable
                ? "成员已停用；历史数据保留。"
                : "成员访问已恢复。电脑需另行恢复授权。",
            );
            await reload(ctx);
          },
          { danger: item.status !== "disabled" },
        ),
      );
      actions.append(
        command(
          ctx,
          `member-sessions-${item.member_id}`,
          "撤销工作台个人会话",
          async () => {
            if (
              !window.confirm(
                `撤销 ${item.email} 的工作台个人会话？电脑上传授权与浏览器登录独立管理。`,
              )
            )
              return;
            await request(
              ctx,
              `/app/api/admin/members/${item.member_id}/revoke-sessions`,
              {},
            );
            note(ctx, "工作台个人会话已撤销。");
          },
        ),
      );
      row.append(actions);
      box.append(row);
    }
    box.append(pager(ctx, "members", data));
    return box;
  }
  async function research(ctx) {
    const box = el("div", null, "project-page");
    box.append(
      el(
        "p",
        "查看已索引的不可变产物与来源关系。这里不会启动 GPU、重建 Dataset 或把评估结果自动当作模型已合格。",
        "banner good",
      ),
    );
    for (const [kind, title, description] of [
      [
        "training",
        "训练记录",
        "训练输入、实验、运行、结果和检查点。任务实时进度在“作业”中。",
      ],
      [
        "evaluations",
        "评估记录",
        "离线、游戏和性能评估的已发布目录。封存评估内容不开放。",
      ],
      ["analyses", "分析记录", "明确发布的分析产物。没有记录时保持空白。"],
    ]) {
      const section = panel(title, description),
        offset = offsets.get(kind) || 0;
      try {
        const data = await request(
          ctx,
          project(`${kind}?limit=25&offset=${offset}`),
        );
        if (data.availability !== "available")
          section.append(
            empty("目录暂不可用", "当前没有可读取的目录权限或索引。"),
          );
        else if (!(data.items || []).length)
          section.append(
            empty(
              "暂无已索引记录",
              "这不等于云存储中没有文件，也不代表该阶段已完成。",
            ),
          );
        else
          for (const item of data.items) {
            const record = panel(show(item.kind), item.artifact_id);
            record.append(
              fields([
                [
                  "记录 / 局数",
                  `${count(item.metadata?.records)} / ${count(item.metadata?.runs)}`,
                ],
                ["文件总大小", bytes(item.payload_bytes)],
                ["索引时间", when(item.indexed_at)],
              ]),
            );
            if (hex(item.artifact_id))
              record.append(
                command(
                  ctx,
                  `research-export-${item.artifact_id}`,
                  "加入导出清单（manifest）",
                  async () => {
                    artifacts.set(item.artifact_id, []);
                    note(
                      ctx,
                      "已选中该产物的 manifest。到“数据下载”生成清单；来源与数据文件不会自动下载。",
                    );
                  },
                ),
              );
            record.append(
              technical(
                {
                  artifact_id: item.artifact_id,
                  producer: item.producer,
                  metadata: item.metadata,
                  parents: item.parents,
                  lineage_partial: item.lineage_partial,
                },
                "精确来源与父产物",
              ),
            );
            section.append(record);
          }
        section.append(pager(ctx, kind, data));
      } catch (error) {
        section.append(empty("暂时无法读取此目录", failure(error)));
      }
      box.append(section);
    }
    box.append(
      link("查看作业状态", route("jobs")),
      link("打开数据下载", route("downloads")),
    );
    return box;
  }
  function exportFacts(ctx, data) {
    const box = panel(
      "固定导出清单",
      "清单记录准确的文件身份。生成清单不等于下载成功，也不会递归抓取父数据或绕过当前共享授权。",
    );
    if (data.schema !== "stpd/project-export-v1" || !hex(data.export_id))
      throw new Error("invalid_export_identity");
    box.append(
      fields([
        ["导出身份", data.export_id],
        [
          "文件数 / 总大小",
          `${count(data.files_count)} / ${bytes(data.total_bytes)}`,
        ],
        ["清单创建时间", when(data.created_at)],
      ]),
    );
    const rows = [];
    for (const file of data.files || []) {
      if (!hex(file.file_id) || !hex(file.sha256))
        throw new Error("invalid_export_file_identity");
      const kind = file.upload_id
        ? "原始录制包"
        : file.type === "manifest"
          ? "产物 manifest"
          : `数据文件 · ${file.role}`;
      const title = el("div");
      title.append(
        el("strong", kind),
        el("span", file.filename, "subtext mono"),
      );
      const cell = local
        ? el("span", "随完整清单校验下载")
        : link(
            "下载此文件",
            member(`exports/${data.export_id}/files/${file.file_id}`),
          );
      if (!local) cell.download = file.filename;
      rows.push([
        title,
        bytes(file.size),
        el("span", file.sha256, "mono"),
        cell,
      ]);
    }
    box.append(table(["文件", "大小", "SHA-256", "下载"], rows));
    const actions = el("div", null, "project-actions");
    const manifestLink = link(
      "保存清单 JSON",
      member(`exports/${data.export_id}`),
    );
    manifestLink.download = data.export_id + ".json";
    actions.append(
      manifestLink,
      link("此清单的固定页面", route("downloads", data.export_id)),
    );
    if (local)
      actions.append(
        command(
          ctx,
          `export-download-${data.export_id}`,
          "下载到本机并逐文件校验",
          async () => {
            await request(
              ctx,
              member(`exports/${data.export_id}/download`),
              {},
            );
            note(
              ctx,
              "本机服务已接收下载请求。下方状态中的文件数与校验结果决定是否完成。",
            );
            await reload(ctx);
          },
          { primary: true },
        ),
      );
    else
      box.append(
        el(
          "p",
          "在云页面可以保存清单与逐文件下载；需要自动逐文件校验和固定目录保存时，请在本机工作台打开同一清单。",
          "muted small",
        ),
      );
    box.append(actions);
    return box;
  }
  function downloadState(value) {
    const box = panel(
      "本机下载状态",
      "仅显示服务已报告的进展。没有百分比或预计完成时间的推算。",
    );
    box.append(
      fields([
        ["状态", show(value.status)],
        ["导出身份", value.export_id || "尚无下载"],
        [
          "已校验 / 总文件",
          `${count(value.verified_files)} / ${count(value.total_files)}`,
        ],
        [
          "已校验 / 总字节",
          `${bytes(value.verified_bytes)} / ${bytes(value.total_bytes)}`,
        ],
      ]),
    );
    if (value.error_code || value.error)
      box.append(
        el(
          "p",
          failure({ message: value.error_code || value.error }),
          "banner error",
        ),
      );
    if (["pending", "downloading"].includes(value.status))
      box.append(
        el("p", "下载仍由本机后台服务处理。关闭网页不表示下载完成。", "muted"),
      );
    if (value.status === "verified")
      box.append(
        el(
          "p",
          "所选文件已通过本机完整性校验。这不表示训练准入或研究质量已通过。",
          "banner good",
        ),
      );
    if (value.directory)
      box.append(fields([["服务管理的本机保存目录", value.directory]]));
    box.append(technical(value, "实际下载回执与观测"));
    return box;
  }
  async function gamesPage(ctx) {
    const data = await request(ctx, member("games"));
    const box = panel("对局与片段", `最近 ${data.profile_limit} 份获共享授权的录制。待整理 ${data.pending_profiles}，整理失败 ${data.failed_profiles}。上传次数不等于独立局数。`);
    box.append(table(["局身份", "完整性", "胜负", "录入 / 接受", "上传来源数"], (data.items || []).map(r => [r.run_id, r.coverage_status || (r.complete ? "完整" : "不完整"), r.outcome === "win" ? "胜利" : r.outcome === "loss" ? "失败" : "未知", `${r.canonical} / ${r.accepted}`, r.uploads.length])));
    for (const failed of data.failures || []) {
      box.append(el("p", `整理失败：${failed.error}`), command(ctx, `retry-profile-${failed.id}`, "重试此整理任务", async () => {
        await request(ctx, member(`datasets/${failed.id}/retry`), {}); await reload(ctx);
      }));
    }
    box.append(link("筛选并建立数据集", route("datasets")), technical(data));
    return box;
  }
  async function decisionDatasets(ctx) {
    const box = panel("建立固定版本数据集", "默认保留可靠决策，允许不完整局和不同环境身份。整包损坏不能跳过校验；失败决策仍保留在报告中。");
    const draft = drafts.get("decision-dataset") || {name: "人类决策数据集", uploads: [], complete: false, wins: false, filters: {}};
    const name = input(box, "数据集名称", "dataset-name", draft.name);
    const complete = input(box, "仅完整局（默认关闭）", "complete-only", draft.complete, "checkbox");
    const noFailures = input(box, "仅无真实记录失败的局（默认关闭）", "no-failures", draft.noFailures, "checkbox");
    const wins = input(box, "仅已确认胜利（未知结果不算胜利）", "wins-only", draft.wins, "checkbox");
    const advanced = el("details");
    advanced.append(el("summary", "可选筛选"));
    const fields = {};
    for (const [key, title] of [["game_version", "游戏版本"], ["connector_version", "连接器版本"], ["annotator_version", "采集器版本"], ["character", "角色"], ["difficulty", "难度"], ["family", "动作类别"], ["surface", "界面"], ["decision_kind", "决策类型"], ["environment_identity", "精确环境身份"]]) {
      fields[key] = input(advanced, `${title}（留空不限，多个值用逗号分隔）`, key, (draft.filters[key] || []).join(","));
    }
    box.append(advanced);
    function save() {
      draft.name = name.value;
      draft.complete = complete.checked;
      draft.wins = wins.checked;
      draft.noFailures = noFailures.checked;
      draft.filters = {};
      for (const [key, field] of Object.entries(fields)) {
        const values = field.value.split(",").map(v => v.trim()).filter(Boolean);
        if (values.length) draft.filters[key] = key === "difficulty" ? values.map(Number) : values;
      }
      drafts.set("decision-dataset", draft);
    }
    for (const field of [name, complete, wins, noFailures, ...Object.values(fields)]) field.onchange = save;
    const listing = await request(ctx, project(`collections?limit=25&offset=${offsets.get("dataset-sources") || 0}`));
    const selection = new Set(draft.uploads);
    for (const item of listing.items || []) {
      const id = item.upload_id || item.id;
      if (!hex(id, 32)) continue;
      const choice = input(box, `${item.summary?.session_id || id} · ${show(item.status)}`, `source-${id}`, selection.has(id), "checkbox");
      choice.disabled = item.status !== "verified";
      choice.onchange = () => {
        if (choice.checked) selection.add(id); else selection.delete(id);
        draft.uploads = [...selection].sort(); save();
      };
    }
    box.append(pager(ctx, "dataset-sources", listing));
    box.append(command(ctx, "preview-dataset", "预览选定记录", async () => {
      save();
      await request(ctx, member("datasets"), {name: draft.name, uploads: draft.uploads,
        rules: {schema: "stpd/decision-selection-v1", complete_only: draft.complete,
          wins_only: draft.wins, no_failures_only: draft.noFailures, filters: draft.filters, seed: 0}, preview_id: null});
      await reload(ctx);
    }));
    const jobs = await request(ctx, member("datasets"));
    const history = panel("预览与生成记录", "后台处理，可离开页面。刷新查看状态。每次生成都是固定产物；新上传不自动加入。");
    for (const job of jobs.items || []) {
      const row = panel(job.request.name, `${show(job.state)} · ${job.request.preview_id ? "生成数据集" : "预览"}`);
      if (job.error) row.append(el("p", `原因：${job.error}。可核对来源后重新预览。`, "banner"));
      if (job.state === "failed") row.append(command(ctx, `retry-dataset-${job.id}`, "重试此任务", async () => {
        await request(ctx, member(`datasets/${job.id}/retry`), {}); await reload(ctx);
      }));
      if (job.result) {
        row.append(facts([["保留决策", job.result.selected ?? job.result.records],
          ["切分状态", job.result.split_status], ["去除精确重复决策", job.result.exact_duplicate_decisions ?? "见产物报告"]]));
        if (job.result.selected_facets) {
          const categories = panel("保留数据的分类", "未知单独保留；下次筛选可使用这里显示的类别值。");
          for (const [key, facet] of Object.entries(job.result.selected_facets)) {
            categories.append(el("p", `${labels[key] || key}：${facet.items.map(x => `${x.value} (${x.count})`).join("、") || "无已知值"}；未知 ${facet.unknown}`));
          }
          row.append(categories);
        }
        if (job.result.runs) {
          row.append(table(["局 / 片段", "完整性", "胜负", "已录入 / 接受"], job.result.runs.map(r => [r.run_id, r.complete ? "完整" : "不完整", r.outcome === "win" ? "胜利" : r.outcome === "loss" ? "失败" : "未知", `${r.canonical} / ${r.accepted}`])));
        }
        if (job.state === "completed" && !job.request.preview_id) {
          row.append(command(ctx, `build-${job.id}`, "按此预览生成固定数据集", async () => {
            await request(ctx, member("datasets"), {name: job.request.name, uploads: job.request.uploads,
              rules: job.request.rules, preview_id: job.id});
            await reload(ctx);
          }));
        }
        if (job.result.artifact_id) row.append(link("查看数据集文件", route("datasets", job.result.artifact_id)), link("下载数据", route("downloads")));
        row.append(technical(job.result, "查看筛选报告与身份"));
      }
      history.append(row);
    }
    box.append(history);
    const catalog = await request(ctx, project(`datasets?limit=25&offset=${offsets.get("dataset-catalog") || 0}`));
    const published = panel("项目已发布数据集", "所有获授权成员可查看，包括原有严格 Full-Run 数据集。具体契约和切分状态见产物详情。");
    for (const item of catalog.items || []) {
      if (hex(item.artifact_id)) published.append(link(item.artifact_id, route("datasets", item.artifact_id)));
    }
    published.append(pager(ctx, "dataset-catalog", catalog));
    box.append(published);
    return box;
  }

  async function exportsPage(ctx) {
    const box = el("div", null, "project-page");
    const requested = new URLSearchParams(location.search).get("id");
    if (requested && !hex(requested))
      throw new Error("invalid_export_identity");
    const chosen = requested || exportId;
    if (requested) box.append(link("建立新的导出清单", route("downloads")));
    if (!requested) {
      const chooser = panel(
        "选择要下载的数据",
        "最多选择 100 份记录或产物。原始录制需有明确项目共享授权；产物仅包含你勾选的自身文件。",
      );
      const offset = offsets.get("export-collections") || 0;
      const listing = await request(
        ctx,
        project(`collections?limit=25&offset=${offset}`),
      );
      const rows = [];
      for (const item of listing.items || []) {
        const id = item.upload_id || item.id;
        if (!hex(id, 32)) continue;
        const available = ["verified", "quarantined"].includes(item.status);
        const checkbox = el("input");
        checkbox.type = "checkbox";
        checkbox.checked = selected.has(id);
        checkbox.disabled = !available;
        checkbox.name = `collection-${id}`;
        checkbox.setAttribute(
          "aria-label",
          `选择录制 ${item.summary?.session_id || id}`,
        );
        checkbox.onchange = () => {
          if (checkbox.checked) selected.add(id);
          else selected.delete(id);
          selectionText.textContent = selectionLabel();
        };
        const description = el("div");
        description.append(
          el("span", item.summary?.session_id || id, "row-title break"),
          el(
            "span",
            `${item.device_id || "电脑未知"} · ${show(item.status)}`,
            "subtext",
          ),
        );
        rows.push([
          checkbox,
          description,
          bytes(item.archive_bytes),
          available ? "生成清单时重新验证共享授权" : "文件尚未接收",
        ]);
      }
      chooser.dataset.projectEditor = "export";
      if (rows.length)
        chooser.append(table(["选择", "录制会话", "包大小", "下载条件"], rows));
      else
        chooser.append(
          empty(
            "当前没有可选择的录制",
            "记录器 Close 后的包被云端接收后会出现在这里。失败记录也可能具有维护价值。",
          ),
        );
      chooser.append(pager(ctx, "export-collections", listing));
      const artifactBox = panel(
          "加入数据集或研究产物",
          "先选择 manifest，再明确勾选数据文件。来源图不会递归下载。",
        ),
        artifactForm = el("div", null, "project-form");
      artifactForm.dataset.projectEditor = "export";
      const artifactDraft = drafts.get("artifact-picker") || {
        kind: "datasets",
        id: "",
      };
      const kind = select(
        artifactForm,
        "产物目录",
        "artifact-kind",
        [
          ["datasets", "数据集"],
          ["models", "模型与结果"],
          ["training", "训练产物"],
          ["evaluations", "评估"],
          ["analyses", "分析"],
        ],
        artifactDraft.kind,
      );
      const artifactInput = input(
        artifactForm,
        "精确产物 ID（可从目录复制）",
        "artifact-id",
        artifactDraft.id,
      );
      artifactInput.maxLength = 64;
      for (const control of [kind, artifactInput])
        control.oninput = () =>
          drafts.set("artifact-picker", {
            kind: kind.value,
            id: artifactInput.value,
          });
      artifactForm.append(
        command(ctx, "inspect-export-artifact", "查看可选文件", async () => {
          const id = artifactInput.value.trim();
          if (!hex(id)) throw new Error("invalid_artifact_identity");
          const response = await request(ctx, project(`${kind.value}/${id}`));
          if (!live(ctx)) return;
          const item = response.item;
          if (!item || item.artifact_id !== id)
            throw new Error("invalid_artifact_identity");
          drafts.set("inspected-artifact", item);
          await reload(ctx);
        }),
      );
      artifactBox.append(
        artifactForm,
        link("浏览数据集目录", route("datasets")),
        link("浏览研究记录", route("research")),
      );
      const inspected = drafts.get("inspected-artifact");
      if (inspected && hex(inspected.artifact_id)) {
        const item = panel(show(inspected.kind), inspected.artifact_id),
          selection = input(
            item,
            "包含该产物的 manifest",
            `artifact-${inspected.artifact_id}`,
            artifacts.has(inspected.artifact_id),
            "checkbox",
          );
        const payloadChoices = [];
        for (const payload of inspected.payloads || []) {
          if (typeof payload.role !== "string" || !hex(payload.sha256))
            continue;
          const choice = input(
            item,
            `${payload.role} · ${bytes(payload.size)}`,
            `role-${payload.role}`,
            (artifacts.get(inspected.artifact_id) || []).includes(payload.role),
            "checkbox",
          );
          choice.disabled = !selection.checked;
          payloadChoices.push([payload.role, choice]);
        }
        const changed = () => {
          for (const [, choice] of payloadChoices)
            choice.disabled = !selection.checked;
          if (selection.checked)
            artifacts.set(
              inspected.artifact_id,
              payloadChoices
                .filter(([, choice]) => choice.checked)
                .map(([role]) => role),
            );
          else artifacts.delete(inspected.artifact_id);
          selectionText.textContent = selectionLabel();
        };
        selection.onchange = changed;
        payloadChoices.forEach(([, choice]) => {
          choice.onchange = changed;
        });
        if (!Array.isArray(inspected.payloads))
          item.append(
            el(
              "p",
              "这条历史索引尚未提供文件角色，只能选择 manifest。管理员显式刷新索引后才可选择数据文件。",
              "banner",
            ),
          );
        artifactBox.append(item);
      }
      chooser.append(artifactBox);
      function selectionLabel() {
        return `已选择 ${selected.size} 份录制、${artifacts.size} 个产物。选择跨页面保留，切换账号会清空。`;
      }
      const selectionText = el("p", selectionLabel(), "project-selection");
      chooser.append(selectionText);
      if (artifacts.size)
        chooser.append(
          technical(
            [...artifacts].map(([artifact_id, roles]) => ({
              artifact_id,
              roles,
            })),
            "已选产物与文件角色",
          ),
        );
      const actions = el("div", null, "project-actions");
      actions.append(
        command(
          ctx,
          "create-export",
          "生成固定导出清单",
          async () => {
            if (
              (!selected.size && !artifacts.size) ||
              selected.size + artifacts.size > 100
            )
              throw new Error("select_between_1_and_100_items");
            const data = await request(ctx, member("exports"), {
              schema: "stpd/project-export-request-v1",
              collections: [...selected].sort(),
              artifacts: [...artifacts].map(([artifact_id, roles]) => ({
                artifact_id,
                roles,
              })),
            });
            if (!hex(data.export_id))
              throw new Error("invalid_export_identity");
            if (!live(ctx)) return;
            exportId = data.export_id;
            note(ctx, "固定清单已生成，文件尚未下载。请核对文件列表再下载。");
            await reload(ctx);
          },
          { primary: true },
        ),
        command(ctx, "clear-export", "清空选择", async () => {
          selected.clear();
          artifacts.clear();
          exportId = null;
          await reload(ctx);
        }),
      );
      chooser.append(actions);
      box.append(chooser);
    }
    if (chosen) {
      try {
        box.append(
          exportFacts(ctx, await request(ctx, member(`exports/${chosen}`))),
        );
      } catch (error) {
        box.append(empty("无法读取这份清单", failure(error)));
      }
    }
    if (local) {
      try {
        box.append(
          downloadState(await request(ctx, member("download-status"))),
        );
      } catch (error) {
        box.append(empty("本机下载状态暂不可用", failure(error)));
      }
    }
    return box;
  }
  const nativeLabels = {
    not_checked: "尚未检查游戏连接",
    game_not_running: "请启动游戏后刷新",
    configured: "目录已绑定，等待游戏连接",
    mismatch: "游戏或录制目录不匹配",
    bound: "游戏连接与录制目录已核对",
    blocked: "游戏连接需要处理",
  };
  const nextSteps = {
    register_collection_tool: "先按安装说明注册项目提供的采集工具，再刷新。",
    prepare_configuration: "确认授权后，准备这台电脑的录制配置。",
    prepare: "准备这台电脑的录制配置。",
    launch_game: "启动游戏，再刷新检查连接。",
    close_game: "先关闭游戏，再绑定录制目录。",
    bind_recording_root: "填写这台电脑的游戏目录，绑定本次录制目录。",
    review_runtime: "游戏身份或录制目录尚未通过检查，请查看连接详情。",
    review_setup: "本机设置需要处理，请查看设置详情中的检查结果。",
    activate_delivery: "游戏连接已核对，可以启用这台电脑的上传。",
    activate: "游戏连接已核对，可以启用这台电脑的上传。",
    none: "真人录制后按 Recorder Close，在采集记录中查看上传与云端收据。",
  };
  function preparationResult(prepared) {
    const result = panel("这台电脑的设置状态");
    const binding = prepared.native_binding || {};
    result.append(
      fields([
        ["本机配置", prepared.configuration_saved === true ? "已保存" : prepared.configuration_saved === false ? "尚未准备" : "状态未取得"],
        ["游戏连接", nativeLabels[binding.status] || "尚未取得连接检查"],
        ["投递配置", prepared.delivery_selected === true ? "当前正在使用" : prepared.delivery_selected === false ? "尚未启用" : "状态未取得"],
        ["后台上传", prepared.delivery_status === "running" ?
          prepared.delivery_selected === true ? "正在运行" : "后台运行中，未选择此配置" :
          prepared.delivery_status === "stopped" ? "已停止" : show(prepared.delivery_status)],
      ]),
      el("p", nextSteps[prepared.next_action] || "请核对本机配置与游戏连接后继续。", "banner"),
    );
    if (prepared.error || binding.reason)
      result.append(el("p", `检查结果：${prepared.error || binding.reason}`, "small muted"));
    result.append(technical(prepared, "设置与连接检查详情"));
    return result;
  }
  function prepareButton(ctx, enrollment) {
    return command(ctx, `prepare-${enrollment.enrollment_id}`, "准备本机录制配置", async () => {
      await request(ctx, member(`campaigns/${enrollment.enrollment_id}/prepare`), {});
      note(ctx, "本机准备已返回。正在重新读取已保存配置与游戏连接状态。");
      await reload(ctx);
    });
  }
  function preparationActions(ctx, enrollment, prepared) {
    const box = el("div", null, "project-actions");
    if (prepared.configuration_saved !== true) {
      if (prepared.configuration_saved === false) box.append(prepareButton(ctx, enrollment));
      else box.append(el("p", "尚未取得本机配置状态，请刷新后再继续。", "muted"));
      return box;
    }
    const binding = prepared.native_binding || {};
    if (binding.status !== "bound") {
      const form = el("div", null, "project-form collection-binding");
      form.dataset.projectEditor = "collection-binding";
      const name = `game-directory:${enrollment.enrollment_id}`;
      const directory = input(form, "这台电脑的游戏安装目录", "game_directory", drafts.get(name) || "");
      directory.placeholder = "选择游戏安装所在的完整路径";
      directory.oninput = () => drafts.set(name, directory.value);
      form.append(command(ctx, `bind-${enrollment.enrollment_id}`, "绑定本机录制目录", async () => {
        const path = directory.value.trim();
        if (!path || !(/^(?:\/|[A-Za-z]:[\\/]|\\\\)/.test(path)))
          throw new Error("absolute_game_directory_required");
        await request(ctx, member(`campaigns/${enrollment.enrollment_id}/bind`), { game_directory: path });
        note(ctx, "目录绑定已返回。请按检查结果启动游戏并刷新。");
        await reload(ctx);
      }, { disabled: binding.game_running === true, title: binding.game_running === true ? "先关闭游戏后绑定目录" : "" }));
      box.append(form);
    }
    box.append(command(ctx, `activate-${enrollment.enrollment_id}`, "启用本机上传", async () => {
      await request(ctx, member(`campaigns/${enrollment.enrollment_id}/activate`), {});
      note(ctx, "已请求启用本机上传。状态以重新读取的后台结果为准。");
      await reload(ctx);
    }, { primary: true, disabled: binding.status !== "bound" ||
      (prepared.delivery_selected === true && prepared.delivery_status === "running") }));
    return box;
  }
  function consentForm(ctx, record, owned) {
    const form = el("div", null, "project-form");
    form.dataset.projectEditor = "campaign";
    const name = `campaign:${record.template_id}`, draft = drafts.get(name) || {};
    const device = select(form, "登记电脑", "device_id",
      owned.map((item) => [item.device_id, item.name || item.device_id]),
      owned.some((item) => item.device_id === draft.device_id) ? draft.device_id : owned[0].device_id);
    const origin = input(form, "确认本次授权范围内的操作来自真人", "human_origin_attested", draft.human_origin_attested, "checkbox");
    const upload = input(form, "授权上传本次授权范围内的新录制", "upload_authorized", draft.upload_authorized, "checkbox");
    const sharing = input(form, "授权项目成员访问这些录制数据", "project_sharing_authorized", draft.project_sharing_authorized, "checkbox");
    const read = () => ({ device_id: device.value, human_origin_attested: origin.checked,
      upload_authorized: upload.checked, project_sharing_authorized: sharing.checked });
    for (const control of [device, origin, upload, sharing])
      control.oninput = control.onchange = () => drafts.set(name, read());
    form.append(command(ctx, `enroll-${record.template_id}`, "确认授权并继续", async () => {
      const value = read();
      if (!value.human_origin_attested || !value.upload_authorized || !value.project_sharing_authorized)
        throw new Error("explicit_campaign_consent_required");
      const result = await request(ctx, member(`campaigns/${record.template_id}/enroll`), {
        device_id: value.device_id, consent: { human_origin_attested: true,
          upload_authorized: true, project_sharing_authorized: true },
      });
      if (!hex(result.enrollment_id, 32) || result.device_id !== value.device_id ||
          result.template_id !== record.template_id) throw new Error("enrollment_identity_mismatch");
      if (!live(ctx)) return;
      drafts.delete(name);
      note(ctx, "授权已保存。继续准备本机配置；游戏录制与后台上传仍需分别检查。");
      await reload(ctx);
    }, { primary: true }));
    return form;
  }
  function defaultAdministration(ctx, settings) {
    const box = panel("日常录制默认设置", "新成员使用此设置确认授权。保存后，已有授权与录制身份保留；新版本需要重新确认。");
    if (local) {
      const target = cloudLink("campaigns");
      if (target) box.append(link("打开云端默认设置 ↗", target));
      return box;
    }
    const form = el("div", null, "project-form collection-settings");
    form.dataset.projectEditor = "collection-settings";
    const previous = settings.default?.template || {}, draft = drafts.get("collection-settings") || previous;
    const name = input(form, "显示名称", "default_name", draft.name || "日常录制");
    const description = input(form, "录制说明", "default_description", draft.description || "记录日常真人游戏，供项目成员查看与研究。");
    const label = el("label", "授权说明", "form-field"), consent = el("textarea");
    consent.name = "default_consent_text"; consent.rows = 4; consent.value = draft.consent_text || "";
    label.append(consent); form.append(label);
    const read = () => ({ name: name.value.trim(), description: description.value.trim(), consent_text: consent.value.trim() });
    for (const control of [name, description, consent]) control.oninput = () => drafts.set("collection-settings", read());
    form.append(command(ctx, "save-default-collection", "发布日常默认设置", async () => {
      const value = read();
      if (!value.name || !value.description || !value.consent_text) throw new Error("default_collection_fields_required");
      await request(ctx, "/app/api/admin/collection-settings", value);
      if (!live(ctx)) return;
      drafts.delete("collection-settings"); note(ctx, "日常默认设置已保存。成员仍须亲自确认授权。");
      await reload(ctx);
    }, { primary: true }));
    box.append(form, el("p", "专题活动可在下方高级选项中发布，或将已发布模板设为日常默认。", "small muted"));
    return box;
  }
  async function collectionFlow(ctx, compact = false, observedStatus = null) {
    const box = panel(compact ? "录制与上传" : "日常录制", local ?
      "这台电脑的设置单独保存。完成一次设置后，日常录制只需保持工作台运行并在游戏中按 Recorder Close。" :
      "在采集电脑的本机工作台完成录制设置。云端查看已收到的上传与已保存授权。");
    const status = local ? observedStatus || await request(ctx, member("collection-status")) : null;
    if (local && (status.schema !== "stpd/local-collection-status-v1" || (status.device_id || null) !== (ctx.identity.device_id || null)))
      throw new Error("collection_status_identity_mismatch");
    const settings = local ? status.settings : await request(ctx, member("collection-settings"));
    if (settings?.schema !== "stpd/collection-settings-v1") throw new Error("unsupported_collection_settings_schema");
    const previous = local ? null : await request(ctx, member("campaigns/enrollments?limit=25&offset=0"));
    const items = status?.items || previous?.items || [];
    const active = local && items.find(item => item.device_id === ctx.identity.device_id &&
      hex(item.enrollment_id, 32) && item.preparation?.delivery_selected === true);
    const record = active ? {template_id: active.template_id, template: active.template} : settings.default;
    const owned = (ctx.identity.devices || []).filter(device => device.ownership === "owned_by_you" && device.active === true &&
      (!local || device.device_id === ctx.identity.device_id));
    const enrolled = active || (record && items.find(item => hex(item.enrollment_id, 32) &&
      item.template_id === record.template_id && item.device_id === ctx.identity.device_id));
    if (!record) box.append(empty("日常录制尚未开放", "管理员设置日常录制说明后，即可确认授权；无需先创建专题活动。"));
    else {
      box.append(el("h3", record.template?.name || "日常录制"), el("p", record.template?.description, "muted"));
      if (active && active.template_id !== settings.default?.template_id)
        box.append(el("p", "当前使用已绑定的录制配置。新的日常默认设置不会改写这份授权或已有记录。", "small muted"));
      if (local) {
        const stages = el("ol", null, "collection-stages");
        for (const [title, detail] of [
          ["账号与电脑", owned.length ? "已登录并绑定当前电脑" : "需要绑定当前电脑"],
          ["录制授权", enrolled ? "授权已保存" : "等待本人确认"],
          ["本机配置", enrolled?.preparation?.configuration_saved === true ? "已保存" : !enrolled || enrolled.preparation?.configuration_saved === false ? "尚未准备" : "状态未取得"],
          ["游戏连接", nativeLabels[enrolled?.preparation?.native_binding?.status] || "尚未检查"],
          ["后台上传", enrolled?.preparation?.delivery_status === "running" && enrolled?.preparation?.delivery_selected === true ? "正在运行" : "尚未确认运行"],
        ]) { const step = el("li"); step.append(el("strong", title), el("span", detail)); stages.append(step); }
        box.append(stages);
      }
      if (!compact) {
        if (!owned.length) box.append(link("登录并绑定采集电脑", route("devices")));
        else if (!enrolled && local) {
          box.append(el("p", record.template?.consent_text, "project-consent"), consentForm(ctx, record, owned));
        }
        if (!local) {
          const saved = items.filter(item => item.template_id === record.template_id);
          if (saved.length) box.append(fields(saved.map(item => ["已授权电脑", item.device_id])));
          box.append(el("p", "请回到采集电脑的工作台确认授权并完成本机设置；云端不会启动本机录制或上传。", "banner"));
        }
        if (enrolled && local) {
          box.append(preparationResult(enrolled.preparation || {}));
          box.append(preparationActions(ctx, enrolled, enrolled.preparation || {}));
        }
        if (local && items.some(item => item.template_id !== record.template_id))
          box.append(el("p", "这台电脑还有其他已保存授权，可在下方高级选项中查看；它们不会被新的默认设置覆盖。", "small muted"));
      }
    }
    if (compact) box.append(link(local ? "继续本机设置 →" : "查看录制设置 →", route("campaigns")));
    else {
      box.append(el("p", "授权声明与本机设置不是已验证的真人来源或完整局证据。云端验收以每份上传的收据为准。", "small muted"),
        link("查看采集记录与上传收据 →", route("collections")));
      if (ctx.identity.principal.role === "admin") box.append(defaultAdministration(ctx, settings));
    }
    box.append(el("p", `设置观测时间：${when(status?.observed_at || settings.observed_at)}`, "small muted"));
    return box;
  }
  async function campaigns(ctx) {
    const box = el("div", null, "project-page");
    let observedStatus = null;
    try {
      if (local) observedStatus = await request(ctx, member("collection-status"));
      box.append(await collectionFlow(ctx, false, observedStatus));
    } catch (error) {
      observedStatus = null;
      box.append(empty("录制设置暂不可用", failure(error)), link("账号与电脑", route("devices")));
    }
    const advanced = el("details", null, "collection-advanced");
    advanced.dataset.preserve = "collection-advanced";
    advanced.append(el("summary", "高级选项：专题活动与已有授权"));
    try { advanced.append(await activityBrowser(ctx, observedStatus)); }
    catch (error) { advanced.append(empty("专题活动暂不可用", failure(error))); }
    box.append(advanced);
    return box;
  }
  async function activityBrowser(ctx, observedStatus) {
    const box = el("div", null, "project-page");
    box.append(
      el(
        "p",
        "专题活动按需使用。日常录制可直接使用上方默认设置；每项授权和本机配置单独保存。",
        "banner good",
      ),
    );
    const data = await request(
      ctx,
      member(`campaigns?limit=25&offset=${offsets.get("campaigns") || 0}`),
    );
    let prior = [];
    try {
      const previous = await request(
        ctx,
        member(
          `campaigns/enrollments?limit=25&offset=${offsets.get("enrollments") || 0}`,
        ),
      );
      prior = previous.items || [];
      const history = panel(
        "已保存的录制授权",
        "这些声明保存在 Hub。重新打开工作台后，可以继续准备当前电脑。",
      );
      if (!(previous.items || []).length)
        history.append(el("p", "尚无有效电脑的活动登记。", "muted"));
      for (const enrollment of previous.items || []) {
        if (!hex(enrollment.enrollment_id, 32) || !hex(enrollment.template_id))
          continue;
        if (local && enrollment.device_id !== ctx.identity.device_id) continue;
        const result = panel(
          enrollment.template?.name || "已登记活动",
          enrollment.campaign_id,
        );
        result.append(
          fields([
            ["登记电脑", enrollment.device_id],
            ["声明时间", when(enrollment.declared_at)],
          ]),
        );
        if (local) {
          try {
            const saved = observedStatus?.items?.find(item => item.enrollment_id === enrollment.enrollment_id &&
              item.device_id === enrollment.device_id && item.template_id === enrollment.template_id);
            const prepared = saved?.preparation || await request(ctx, member(`campaigns/${enrollment.enrollment_id}/preparation`));
            result.append(preparationResult(prepared), preparationActions(ctx, enrollment, prepared));
          } catch (error) { result.append(empty("本机设置暂不可用", failure(error))); }
        } else
          result.append(
            el(
              "p",
              "在这台采集电脑的工作台打开“录制与上传”，继续本机设置。",
              "muted",
            ),
          );
        history.append(result);
      }
      history.append(pager(ctx, "enrollments", previous));
      box.append(history);
    } catch (error) {
      box.append(empty("历史活动登记暂不可用", failure(error)));
    }
    const allOwned = (ctx.identity.devices || []).filter(
      (device) => device.ownership === "owned_by_you" && device.active === true,
    );
    const owned = local
      ? allOwned.filter((device) => device.device_id === ctx.identity.device_id)
      : allOwned;
    if (!owned.length) {
      const notice = panel(
        "先绑定采集电脑",
        local
          ? "这台电脑尚未绑定到当前账号，或上传授权已停用。"
          : "当前账号没有有效的自有电脑。请在采集电脑的工作台发起绑定。",
      );
      notice.append(link("账号与电脑", route("devices")));
      box.append(notice);
    }
    if (!(data.templates || []).length)
      box.append(
        empty(
          "暂无发布的采集活动",
          "需要专题采集时，管理员可发布活动模板；日常录制无需单独建立活动。",
        ),
      );
    for (const record of data.templates || []) {
      const template = record.template;
      if (!template || !hex(record.template_id)) continue;
      const row = panel(template.name, template.description);
      row.append(
        badge(`版本 ${count(template.version)}`),
        fields([
          ["软件要求", template.schema === "stpd/collection-activity-v2" ? "在采集电脑检查当前游戏与工具" : template.game?.version],
          ["共享范围", "项目成员"],
          ["活动 ID", template.activity_id],
        ]),
        el("p", template.consent_text, "project-consent"),
      );
      row.append(
        technical(
          {
            template_id: record.template_id,
            platform_source_revision: template.platform_source_revision,
            evidence_source_revision: template.evidence_source_revision,
            tool_release_id: template.tool_release_id,
            game: template.game,
            mod: template.mod,
          },
          "核对活动要求的精确软件身份",
        ),
      );
      const available = owned.filter(device => !prior.some(item =>
        item.template_id === record.template_id && item.device_id === device.device_id));
      if (available.length) row.append(consentForm(ctx, record, available));
      if (!local && ctx.identity.principal.role === "admin")
        row.append(command(ctx, `default-${record.template_id}`, "设为日常默认", async () => {
          await request(ctx, "/app/api/admin/collection-settings", { template_id: record.template_id });
          note(ctx, "默认模板已更新。已有授权与录制身份保留。");
          await reload(ctx);
        }));
      box.append(row);
    }
    box.append(pager(ctx, "campaigns", data));
    if (ctx.identity.principal.role === "admin") {
      const help = panel(
        "管理员发布活动",
        "活动模板不可变，修改必须发布递增版本。软件身份与授权文本需要经过项目审核。",
      );
      if (local) {
        const target = cloudLink("campaigns");
        if (target) help.append(link("打开云端活动管理 ↗", target));
      } else {
        const form = el("div", null, "project-form");
        form.dataset.projectEditor = "campaign-template";
        const label = el("label", "经审核的活动模板 JSON", "form-field"),
          text = el("textarea");
        text.name = "campaign-template";
        text.rows = 10;
        text.value = drafts.get("campaign-template") || "";
        text.oninput = () => drafts.set("campaign-template", text.value);
        label.append(text);
        form.append(label);
        form.append(
          command(ctx, "publish-campaign", "核对后发布模板", async () => {
            let value;
            try {
              value = JSON.parse(text.value);
            } catch {
              throw new Error("invalid_template_json");
            }
            if (value?.schema !== "stpd/collection-activity-v1")
              throw new Error("invalid_template_schema");
            if (
              !window.confirm(
                `发布活动“${value.name || "未命名"}”版本 ${value.version}？发布后不能改写该版本。`,
              )
            )
              return;
            await request(ctx, "/app/api/admin/campaigns", value);
            if (!live(ctx)) return;
            drafts.delete("campaign-template");
            note(ctx, "活动模板已发布。");
            await reload(ctx);
          }),
        );
        help.append(form);
      }
      box.append(help);
    }
    return box;
  }
  function readinessPanel(value) {
    const box = panel(
      "加载前检查",
      "文件、代码和软件包检查与游戏实时兼容性是不同关卡。",
    );
    box.append(
      badge(
        show(value.status),
        value.status === "ready_to_load" ? "good" : "wait",
      ),
    );
    box.append(
      table(
        ["检查", "结果", "原因"],
        Object.entries(value.checks || {}).map(([key, item]) => [
          show(key),
          item.status === "pass" ? "通过" : show(item.status),
          item.code || "—",
        ]),
      ),
    );
    box.append(
      el(
        "p",
        "游戏环境会在 Runtime 首次决策前核对；权重由适配器加载时检查。检查通过不代表模型已经加载或评估通过。",
        "small muted",
      ),
    );
    return box;
  }
  function localStatus(ctx, data) {
    const box = panel(
      "本机运行状态",
      "状态来自本机服务与其管理的唯一 Runtime。操作请求已接收与执行成功分开显示。",
    );
    const runtime = data.runtime,
      operation = data.operation;
    box.append(
      fields([
        ["本机服务", show(data.status)],
        ["模型加载", data.loaded === true ? "服务报告已加载" : "尚未确认加载"],
        ["Runtime 模式", runtime ? show(runtime.mode) : "尚无 Runtime 观测"],
        [
          "控制器",
          runtime?.controller === "held"
            ? "Runtime 持有"
            : runtime?.controller === "released"
              ? "已释放"
              : "未知",
        ],
        [
          "最近操作",
          operation
            ? `${show(operation.action)} · ${show(operation.status)}`
            : "无",
        ],
      ]),
    );
    if (data.error_code)
      box.append(
        el("p", failure({ message: data.error_code }), "banner error"),
      );
    if (data.observation_error)
      box.append(
        el(
          "p",
          "当前无法取得新的 Runtime 状态。以下保留的是此前观测，不能据此继续执行模型决策。",
          "banner error",
        ),
      );
    if (
      data.status === "command_unknown" ||
      data.status === "recovery_required" ||
      runtime?.tainted
    )
      box.append(
        el(
          "p",
          "结果未确认或 Runtime 已 tainted。禁止重复决策，请明确交还人类或停止并审查证据。",
          "banner error",
        ),
      );
    const actions = el("div", null, "project-actions");
    const recoverable = data.loaded === true || Boolean(data.previous_session);
    const changing = operation?.status === "pending";
    const safe =
      data.loaded === true &&
      runtime?.lifecycle === "running" &&
      !changing &&
      !data.observation_error &&
      !runtime?.tainted &&
      ![
        "command_unknown",
        "recovery_required",
        "runtime_exited",
        "stopped",
      ].includes(data.status);
    for (const [action, label] of [
      ["shadow", "Shadow · 只评分"],
      ["one_step", "执行一个决策"],
      ["auto", "开始自动决策"],
      ["human", "交还人类控制"],
      ["stop", "停止并封装评估"],
    ]) {
      const recovery = ["human", "stop"].includes(action);
      actions.append(
        command(
          ctx,
          `model-command-${action}`,
          label,
          async () => {
            if (
              ["one_step", "auto"].includes(action) &&
              !window.confirm(
                "此操作会在本机真实游戏中执行模型决策。请确认已退出真人采集，并准备好随时交还人类控制。",
              )
            )
              return;
            await request(ctx, "/api/local-models/command", { action });
            note(
              ctx,
              "本机服务已接收操作；请查看服务状态与 Runtime 回执。未知结果不会自动重发。",
            );
            await reload(ctx);
          },
          {
            disabled: recovery ? !recoverable : !safe,
            danger: action === "stop",
          },
        ),
      );
    }
    box.append(actions);
    if (runtime)
      box.append(
        technical(
          {
            run_id: runtime.run_id,
            lifecycle: runtime.lifecycle,
            tainted: runtime.tainted,
            taint_reason: runtime.taint_reason,
            last_decision: runtime.last_decision,
            last_receipt: runtime.last_receipt,
            environment: runtime.environment,
          },
          "决策、回执与精确运行身份",
        ),
      );
    if (data.evaluation) box.append(evaluationPanel(data.evaluation));
    return box;
  }
  function evaluationPanel(value) {
    const box = panel(
      "本机已封装的评估记录",
      "这是有界 Runtime 操作与证据检查结果，不是游戏胜率或训练准入。",
    );
    box.append(
      fields([
        ["模型选择", value.selection_id],
        ["run ID", value.run_id],
        ["证据验证", value.evidence_verification || "未提供"],
        ["事件数", count(value.event_count)],
        [
          "游戏结果",
          value.game_outcome === "not_measured"
            ? "未测量"
            : value.game_outcome || "未知",
        ],
      ]),
      technical(value),
    );
    return box;
  }
  async function localModels(ctx) {
    const box = el("div", null, "project-page");
    if (!local) {
      box.append(
        empty(
          "请在游戏所在电脑打开工作台",
          "云页面不会远程启动或控制游戏。模型下载、加载和真实游戏评估由本机服务负责。",
        ),
      );
      return box;
    }
    let catalog, state;
    const replies = await Promise.allSettled([
      request(ctx, "/api/local-models"),
      request(ctx, "/api/local-models/status"),
    ]);
    if (replies[0].status === "fulfilled") catalog = replies[0].value;
    if (replies[1].status === "fulfilled") state = replies[1].value;
    if (state) box.append(localStatus(ctx, state));
    else
      box.append(
        empty(
          "本机 Runtime 状态暂不可用",
          "执行控件保持关闭。请刷新状态，不要重复之前的命令。",
        ),
      );
    const preparations = panel(
      "准备审核过的运行组合",
      "安装固定版本 Runtime 不会启动游戏；每次加载默认保持人类控制。",
    );
    preparations.append(
      command(
        ctx,
        "install-runtime",
        "安装 / 校验固定 Runtime",
        async () => {
          await request(ctx, "/api/local-models/install-runtime", {});
          note(ctx, "Runtime 安装请求已接收。请查看实际操作状态。");
          await reload(ctx);
        },
        {
          disabled:
            !state ||
            state.loaded === true ||
            state.operation?.status === "pending" ||
            ["command_unknown", "recovery_required"].includes(state.status),
        },
      ),
    );
    if (!catalog)
      preparations.append(
        empty("模型选择目录暂不可用", "不会根据任意下载文件或路径启动代码。"),
      );
    else if (!(catalog.policies || []).length)
      preparations.append(
        empty(
          "暂无审核过的模型选择",
          "普通训练模型与可在游戏内运行的适配器组合不是同一个东西。",
        ),
      );
    for (const item of catalog?.policies || []) {
      if (!selectionId(item.selection_id)) continue;
      const row = panel(
        item.label || item.selection_id,
        "模型、适配器、输入表示与环境契约作为一个审核过的选择。",
      );
      row.append(
        technical({
          selection_id: item.selection_id,
          artifact_sha256: item.artifact_sha256,
          support: item.support,
          claims: item.claims,
        }),
      );
      const report = readiness.get(item.selection_id);
      const actions = el("div", null, "project-actions");
      actions.append(
        command(
          ctx,
          `model-readiness-${item.selection_id}`,
          "检查本机加载条件",
          async () => {
            const result = await request(
              ctx,
              "/api/local-models/readiness?selection_id=" +
                encodeURIComponent(item.selection_id),
            );
            if (result.selection_id !== item.selection_id)
              throw new Error("model_identity_mismatch");
            if (!live(ctx)) return;
            readiness.set(item.selection_id, result);
            await reload(ctx);
          },
        ),
        command(
          ctx,
          `model-start-${item.selection_id}`,
          "加载 · 保持人类控制",
          async () => {
            await request(ctx, "/api/local-models/start", {
              selection_id: item.selection_id,
            });
            note(
              ctx,
              "本机服务已接收加载请求。模型尚需完成实际加载与身份核对。",
            );
            await reload(ctx);
          },
          {
            primary: true,
            disabled:
              !state ||
              state.loaded === true ||
              state.operation?.status === "pending" ||
              ["command_unknown", "recovery_required"].includes(state.status) ||
              report?.status !== "ready_to_load",
          },
        ),
      );
      row.append(actions);
      if (report) row.append(readinessPanel(report));
      preparations.append(row);
    }
    box.append(preparations);
    const downloads = panel(
      "下载模型产物",
      "下载只保存并验证文件，不会自动安装适配器或激活模型。",
    );
    if (!signedIn(ctx))
      downloads.append(
        el("p", "登录项目账号后可查看模型目录。已有本机模型仍按本机权限管理。"),
      );
    else {
      try {
        const models = await request(ctx, project("models?limit=25&offset=0"));
        const entries = (models.items || []).filter(
          (item) => item.kind === "model" && hex(item.artifact_id),
        );
        if (!entries.length)
          downloads.append(
            empty(
              "当前页没有已发布模型",
              "训练作业完成后需要发布有效模型产物，才会进入目录。",
            ),
          );
        for (const item of entries)
          downloads.append(
            command(
              ctx,
              `model-download-${item.artifact_id}`,
              `下载模型 ${item.artifact_id.slice(0, 12)}… · ${bytes(item.payload_bytes)}`,
              async () => {
                await request(ctx, "/api/local-models/download", {
                  artifact_id: item.artifact_id,
                });
                note(ctx, "模型下载请求已接收。以本机下载回执为准，尚未加载。");
                await reload(ctx);
              },
              {
                disabled:
                  !state ||
                  state.operation?.status === "pending" ||
                  ["command_unknown", "recovery_required"].includes(
                    state.status,
                  ),
              },
            ),
          );
        if (models.total > 25)
          downloads.append(
            el(
              "p",
              "这里仅显示目录前 25 项；完整模型目录可查看其余身份。",
              "small muted",
            ),
          );
      } catch (error) {
        downloads.append(empty("云端模型目录暂不可用", failure(error)));
      }
      downloads.append(link("查看完整模型目录", route("models")));
    }
    for (const item of catalog?.downloaded_models || []) {
      const downloaded = panel("已下载的模型", item.artifact_id);
      downloaded.append(
        badge(item.local_download ? "存在本机下载记录" : "下载尚未确认"),
        el(
          "p",
          item.support_status === "unsupported"
            ? "当前没有匹配的游戏适配器与输入表示校验，不能直接在游戏中运行。"
            : show(item.support_status),
          "muted",
        ),
      );
      downloads.append(downloaded);
    }
    box.append(downloads);
    if (catalog?.evaluations?.length) {
      const evaluations = panel(
        "本机评估历史",
        "最多保留展示 100 条已校验的本地评估记录；不会自动上传。",
      );
      for (const value of catalog.evaluations)
        evaluations.append(evaluationPanel(value));
      box.append(evaluations);
    }
    return box;
  }
  return {
    reload: async () => {},
    async render(view, identity) {
      if (!supported.has(view)) throw new Error("unsupported_project_view");
      const nextAccount = `${identity?.principal?.subject || "anonymous"}:${identity?.principal?.role || ""}:${identity?.status || ""}`;
      if (account !== nextAccount) {
        account = nextAccount;
        offsets = new Map();
        drafts = new Map();
        selected = new Set();
        artifacts = new Map();
        exportId = null;
        readiness = new Map();
      }
      const ctx = {
        account,
        key: `${account}:${view}:${location.search}`,
        identity,
        scope: scope(),
      };
      current = ctx;
      if (view !== "local-models" && !signedIn(ctx)) return authNotice(ctx);
      try {
        return await {
          members: admin,
          statistics,
          datasets: decisionDatasets,
          games: gamesPage,
          downloads: exportsPage,
          research,
          "local-models": localModels,
          campaigns,
          "collection-overview": (ctx) => collectionFlow(ctx, true),
        }[view](ctx);
      } catch (error) {
        const box = panel("当前页面暂不可用", failure(error));
        box.append(
          link("账号与电脑", route("devices")),
          command(ctx, "retry-read", "重新读取状态", () => reload(ctx)),
        );
        return box;
      }
    },
  };
})();
