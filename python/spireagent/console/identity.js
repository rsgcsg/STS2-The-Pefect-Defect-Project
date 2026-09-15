"use strict";

// Same account and views in both shells. Credentials remain in their owning servers.
window.SpireIdentity = (() => {
  const local = document.body.dataset.mode === "local";
  let identity = null, checked = 0, busy = null, scope = local ? "local" : "project";
  let deviceDraft = null;
  let timer = null, refreshPage = () => {}, epoch = 0, loggingOut = false;
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  async function request(path, body, csrf) {
    const response = await fetch(path, {
      method: body ? "POST" : "GET", cache: "no-store", credentials: "same-origin",
      redirect: "error", signal: AbortSignal.timeout(10000),
      headers: body ? {"Content-Type": "application/json", "X-CSRF-Token": csrf || ""} : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const value = await response.json();
    if (!response.ok || value.error) throw new Error(value.error || "服务暂不可用");
    return value;
  }
  function message(text) { document.getElementById("notice").textContent = text; }
  function action(title, handler) {
    const b = el("button", title, "button secondary"); b.type = "button";
    b.onclick = async () => {
      b.disabled = true;
      try { await handler(); }
      catch (error) { message(`暂未完成：${error.message}。本机录制仍可继续。`); }
      finally { b.disabled = false; }
    };
    return b;
  }
  function topbar() {
    const target = document.getElementById("account-actions"); target.replaceChildren();
    const principal = identity?.principal;
    const memberLink = document.querySelector('[data-view="members"]');
    if (memberLink) memberLink.hidden = principal?.role !== "admin";
    if (principal && (!local || identity.status === "signed_in")) {
      target.append(el("span", principal.email, "account-label"));
      target.append(action("退出账号", async () => {
        clearTimeout(timer);
        const csrf = identity.csrf_token;
        loggingOut = true; epoch++; busy = null; identity = null; scope = "local";
        topbar(); refreshPage(true);
        document.getElementById("content").replaceChildren();
        if (!local) { location.assign("/cdn-cgi/access/logout"); return; }
        let result;
        try { result = await request("/api/identity/logout", {}, csrf); }
        finally { loggingOut = false; epoch++; }
        identity = null; checked = 0; scope = "local";
        await refresh(true); refreshPage(true);
        message(result.remote_revoked ? "已退出账号；这台电脑的上传授权保留。" :
          "已退出本机账号；云端会话未确认撤销，将按有效期失效。上传授权保留。");
      }));
    } else if (local) {
      target.append(action(identity?.status === "reconnect_required" ? "重新登录" : "登录项目账号",
        () => { location.assign("?view=devices"); }));
    }
    const select = document.getElementById("device-scope"), previous = scope;
    select.replaceChildren();
    if (local) { const option = el("option", "这台电脑 · 本地记录与队列"); option.value = "local"; select.append(option); }
    if (principal) {
      const option = el("option", principal.project_shared ? "项目 · 全部共享数据" : "项目 · 获授权数据"); option.value = "project"; select.append(option);
      for (const device of identity.devices || []) {
        const option = el("option", device.name || device.device_id);
        option.value = device.device_id; select.append(option);
      }
    }
    if (![...select.options].some(o => o.value === previous)) scope = local ? "local" : "project";
    select.value = scope;
    select.onchange = () => { scope = select.value; epoch++; refreshPage(true); };
  }
  async function refresh(force = false) {
    if (loggingOut) return identity;
    if (!force && Date.now() - checked < 30000) return identity;
    if (busy) return busy;
    const version = epoch;
    const task = (async () => {
      let next;
      try {
        next = await request(local ? "/api/identity" : "/app/api/identity");
        if (!local) next.status = "signed_in";
      } catch (error) {
        next = {status: "unavailable", error: error.message};
      }
      if (version !== epoch) return identity;
      if (identity?.principal?.subject !== next?.principal?.subject) epoch++;
      identity = next; checked = Date.now(); topbar(); return identity;
    })();
    busy = task;
    try { return await task; } finally { if (busy === task) busy = null; }
  }
  function api(route, query) {
    if (!local || scope !== "local") {
      const params = new URLSearchParams(query);
      if (scope !== "project" && scope !== "local") params.set("device", scope);
      return (local ? "/api/project/" : "/app/api/") + route +
        (params.size ? "?" + params : "");
    }
    return "/api/console/" + route + query;
  }
  async function waitForApproval() {
    clearTimeout(timer);
    try {
      const result = await request("/api/identity/poll", {}, identity.csrf_token);
      if (result.status === "pending") timer = setTimeout(waitForApproval, 3000);
      else if (result.status === "approved") {
        scope = "project"; await refresh(true); refreshPage(true);
        message("登录与设备绑定完成。后台上传与个人登录分别管理。");
      } else { await refresh(true); refreshPage(); message("本次绑定已结束；需要时可重新发起。"); }
    } catch (error) { message(`暂时无法确认绑定：${error.message}。点击“检查绑定结果”可继续。`); }
  }
  function flowCard(flow) {
    const box = el("div", undefined, "onboarding-step");
    box.append(el("h3", "在浏览器中确认"), el("p", "核对电脑名称及配对码，只批准刚刚由你发起的请求。"));
    box.append(el("strong", flow.user_code, "pair-code"));
    const link = el("a", "打开登录与绑定页面 ↗", "button");
    link.href = flow.approval_url; link.target = "_blank"; link.rel = "noreferrer";
    box.append(link, action("检查绑定结果", waitForApproval));
    return box;
  }
  function renderDevices() {
    const box = el("section", undefined, "panel onboarding"), who = identity?.principal;
    box.append(el("h2", who ? "账号与项目电脑" : "接入 SpireAgent"));
    box.append(el("p", "使用项目邀请的邮箱接入；首次验证后自动建立项目账号，无需另设密码。"));
    box.append(el("p", "每条电脑记录对应一份工作台配置；同一台电脑可以有多份。退出登录不会转移设备归属或已有数据。"));
    if (local) {
      box.append(el("p", identity?.device_credential_present ?
        "这台电脑已保存上传凭据；是否有效以 Hub 最近验证为准。个人退出不会删除它。" :
        "先登录并确认电脑名称。绑定成功后，打开“录制与上传”确认日常录制授权并完成本机设置；登录不代表同意上传。"));
      if (!identity?.hub_configured) box.append(el("p", "尚未配置项目 Hub 地址。请使用项目提供的启动配置。"));
      else if (!who || identity.status !== "signed_in") {
        const label = el("label", "这台电脑的名称"), input = el("input");
        input.type = "text"; input.maxLength = 80; input.value = deviceDraft ?? identity?.device_name ?? "我的电脑";
        input.id = "device-name"; input.addEventListener("input", () => { deviceDraft = input.value; });
        label.append(input); box.append(label);
        box.append(action("登录并绑定这台电脑", async () => {
          const flow = await request("/api/identity/login", {device_name: input.value.trim()}, identity.csrf_token);
          await refresh(true); refreshPage();
          message("请打开登录页面，使用项目邮箱完成确认。");
          if (flow) timer = setTimeout(waitForApproval, 3000);
        }));
      }
      if (identity?.flow) box.append(flowCard(identity.flow));
      if (identity?.device_credential_present && identity?.delivery_configured) box.append(action("恢复已修正授权的上传", async () => {
        const result = await request("/api/identity/resume-uploads", {}, identity.csrf_token);
        message(`已恢复 ${result.resumed} 条认证阻塞记录；其他失败与原始证据保留。`);
        refreshPage();
      }));
      box.append(el("p", identity?.delivery_configured ?
        "这台电脑已有投递配置；在“录制与上传”查看本机检查，在“这台电脑”的采集记录中查看上传与云端收据。" :
        "当前尚未配置投递。打开“录制与上传”，确认日常录制授权并查看本机设置的下一步。"));
    }
    if (who) {
      const recording = el("a", "继续录制与上传 →", "button");
      recording.href = "?view=campaigns";
      box.append(recording);
      box.append(el("p", `当前账号：${who.email} · ${who.role}`));
      for (const device of identity.devices || []) {
        const row = el("div", undefined, "device-row");
        row.append(el("strong", device.name || device.device_id), el("code", device.device_id));
        row.append(el("span", device.active === true ? "设备上传授权有效" : device.active === false ? "设备上传授权已撤销" : "设备授权状态未知"));
        row.append(el("span", device.last_seen ? `最近联络：${new Date(device.last_seen).toLocaleString()}（不代表当前在线）` : "尚未收到设备联络；在线状态未知"));
        row.append(action("查看这台电脑的云端数据", async () => { scope = device.device_id; topbar(); history.pushState({}, "", "?view=collections"); refreshPage(); }));
        row.append(el("span", device.ownership === "owned_by_you" ? "由你管理" : "项目共享信息"));
        if (!local && device.can_revoke === true) row.append(action("撤销这台电脑授权", async () => {
          if (!window.confirm("撤销后这台电脑不能继续上传，历史数据保留。恢复授权需要重新办理，确定撤销？")) return;
          await request("/app/api/identity/devices/" + encodeURIComponent(device.device_id) + "/revoke",
            {csrf_token: identity.csrf_token}, identity.csrf_token);
          await refresh(true); refreshPage(true);
        }));
        if (local && device.can_revoke === true) row.append(el("span", "设备授权管理：打开云端 → 账号与电脑"));
        box.append(row);
      }
      if (!(identity.devices || []).length) box.append(el("p", "账号下尚无电脑。请在要采集的电脑上打开工作台并发起绑定。"));
    }
    if (identity?.error) box.append(el("p", `账号连接暂不可用：${identity.error}；未显示缓存的私人项目数据。`));
    return box;
  }
  async function renderConnect() {
    const box = el("section", undefined, "panel onboarding");
    const flow = new URLSearchParams(location.search).get("flow");
    if (local || !/^[a-f0-9]{32}$/.test(flow || "")) throw new Error("无效绑定请求");
    const facts = await request("/app/api/identity/flows/" + flow);
    box.append(el("h2", "确认接入这台电脑"), el("p", `账号：${identity?.principal?.email || "当前登录账号"}`));
    box.append(el("h3", facts.device_name), el("strong", facts.user_code, "pair-code"));
    box.append(el("p", facts.purpose === "connect_existing_device" ?
      `重新连接已有电脑：${facts.device_id}` : "注册一台新的采集电脑"));
    box.append(el("p", "请与本机工作台显示的配对码核对。批准后，此电脑获得独立上传凭据，工作台可查看你获授权的项目数据。不会启动游戏、训练或自动同意上传数据。"));
    if (facts.status === "pending" && facts.approval_allowed) box.append(action("确认是我的电脑，批准接入", async () => {
      await request("/app/api/identity/flows/" + flow + "/approve", {
        csrf_token: identity.csrf_token, user_code: facts.user_code,
      }, identity.csrf_token);
      box.replaceChildren(el("h2", "已批准"), el("p", "回到本机工作台，绑定结果会自动更新。这个页面可以关闭。"));
    }));
    else box.append(el("p", facts.status === "pending" ? "当前账号没有绑定这台电脑的权限。请使用受邀请且获授权的账号。" : `请求状态：${facts.status}。请回到本机工作台查看结果。`));
    if (facts.status === "pending") box.append(action("不是我的请求，拒绝", async () => {
      await request("/app/api/identity/flows/" + flow + "/deny", {
        csrf_token: identity.csrf_token, user_code: facts.user_code,
      }, identity.csrf_token);
      box.replaceChildren(el("h2", "已拒绝"), el("p", "没有发放任何设备或个人凭据。可关闭此页面。"));
    }));
    return box;
  }
  return {refresh, api, renderDevices, renderConnect,
    ensureProjectScope() {
      if (scope === "local" && identity?.principal && identity.status === "signed_in") {
        scope = "project"; epoch++; topbar();
      }
    },
    connect(fn) { refreshPage = fn; },
    isLocal() { return local && scope === "local"; },
    context() { return `${scope}:${identity?.principal?.subject || "anonymous"}:${epoch}`; },
  };
})();
