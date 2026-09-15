import http from "node:http";
import { URL } from "node:url";

import { POLICY_RUNTIME_MODES, PolicyRuntimeError, validatePolicyMode } from "./policy-runtime-client.mjs";

function send(response, statusCode, contentType, body) {
  response.writeHead(statusCode, {
    "content-type": contentType,
    "cache-control": "no-store",
    "content-length": Buffer.byteLength(body)
  });
  response.end(body);
}

const MAX_REQUEST_BYTES = 16 * 1024;

function normalizeHost(value) {
  return typeof value === "string" ? value.trim().toLowerCase().replace(/^\[|\]$/gu, "") : "";
}

export function isLoopbackHost(value) {
  const host = normalizeHost(value);
  if (host === "localhost" || host === "::1") return true;
  const octets = host.split(".");
  return octets.length === 4
    && octets[0] === "127"
    && octets.slice(1).every((octet) => /^\d+$/u.test(octet) && Number(octet) >= 0 && Number(octet) <= 255);
}

function isLoopbackAddress(value) {
  const host = normalizeHost(value).replace(/^::ffff:/u, "");
  return isLoopbackHost(host);
}

async function readJsonBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_REQUEST_BYTES) {
      throw new PolicyRuntimeError("Request body is too large", "invalid_request");
    }
    chunks.push(chunk);
  }
  if (chunks.length === 0) throw new PolicyRuntimeError("Request body is required", "invalid_request");
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new PolicyRuntimeError("Request body must be valid JSON", "invalid_request");
  }
}

function decodeModeCommand(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)
      || Object.keys(value).length !== 1 || !Object.hasOwn(value, "mode")) {
    throw new PolicyRuntimeError("Mode command must contain only mode", "invalid_request");
  }
  return validatePolicyMode(value.mode);
}

function policyRequestError(request, bindHost) {
  const authority = request.headers.host;
  const localHost = normalizeHost(bindHost);
  const hosts = new Set(["127.0.0.1", "localhost", "::1", localHost]);
  const allowed = [...hosts].map((host) => `${host.includes(":") ? `[${host}]` : host}:${request.socket.localPort}`);
  const hostCount = request.rawHeaders.filter((value, index) => index % 2 === 0 && value.toLowerCase() === "host").length;
  if (hostCount !== 1 || !allowed.includes(authority)) return { status: 403, error: "policy_request_host_not_allowed" };
  if (request.headers.origin !== undefined && request.headers.origin !== `http://${authority}`) return { status: 403, error: "policy_request_origin_not_allowed" };
  if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/iu.test(request.headers["content-type"] ?? "")) return { status: 415, error: "policy_request_requires_application_json" };
  return null;
}

export function createWorkbenchServer(service, options = {}) {
  const bindHost = options.bindHost ?? null;
  const mutatingCommandsAllowed = isLoopbackHost(bindHost);
  const readOnly = !mutatingCommandsAllowed;
  const readStatus = async () => {
    const status = await service.readStatus();
    return readOnly ? { ...status, read_only: true } : status;
  };

  return http.createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    if (request.method === "GET" && url.pathname === "/api/status") {
      const status = await readStatus();
      send(response, 200, "application/json; charset=utf-8", `${JSON.stringify(status)}\n`);
      return;
    }
    if (request.method === "GET" && url.pathname === "/") {
      send(response, 410, "application/json; charset=utf-8", JSON.stringify({
        error: "project_console_moved",
        message: "Use npm run workbench at the project root. This endpoint retains diagnostics APIs only."
      }));
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/policy/mode") {
      if (!mutatingCommandsAllowed || !isLoopbackAddress(request.socket.localAddress)) {
        request.resume();
        send(response, 403, "application/json; charset=utf-8", `${JSON.stringify({
          error: "policy_mutation_loopback_only",
          message: "Policy Runtime mutating commands are available only on a loopback Workbench bind."
        })}\n`);
        return;
      }
      const denied = policyRequestError(request, bindHost);
      if (denied) {
        request.resume();
        send(response, denied.status, "application/json; charset=utf-8", `${JSON.stringify({ error: denied.error })}\n`);
        return;
      }
      try {
        const mode = decodeModeCommand(await readJsonBody(request));
        const result = await service.setPolicyMode(mode);
        send(response, 200, "application/json; charset=utf-8", `${JSON.stringify({
          schema: "sts2.workbench/mode-command-1",
          mode,
          status: result.status,
          tick: result.tick ?? null
        })}\n`);
      } catch (error) {
        const code = error?.code ?? "policy_runtime_unavailable";
        const statusCode = code === "invalid_request" || code === "policy_runtime_invalid_mode"
          ? 400
          : code === "policy_runtime_invalid_schema" ? 502 : 503;
        send(response, statusCode, "application/json; charset=utf-8", `${JSON.stringify({
          error: code,
          message: error instanceof Error ? error.message : String(error),
          allowed_modes: POLICY_RUNTIME_MODES
        })}\n`);
      }
      return;
    }
    if ((url.pathname === "/api/status" || url.pathname === "/")
        && request.method !== "GET") {
      send(response, 405, "application/json; charset=utf-8", JSON.stringify({
        error: "method_not_allowed"
      }));
      return;
    }
    if (request.method !== "GET" && request.method !== "POST") {
      send(response, 405, "application/json; charset=utf-8", JSON.stringify({
        error: "method_not_allowed"
      }));
      return;
    }
    send(response, 404, "application/json; charset=utf-8", JSON.stringify({
      error: "not_found"
    }));
  });
}
