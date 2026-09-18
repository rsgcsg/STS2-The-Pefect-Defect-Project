import {
  EnvironmentControllerSession,
  PlayerEnvironmentHttpError,
  prefetchPlayerEnvironmentDecisionBundle,
  type EnvironmentControlClient,
  type EnvironmentControllerSession as ControllerSession
} from "@rsgcsg/sts2-connector-client";
import { POLICY_RUNTIME_VERSION, type ConnectorAdapterClient, type DecisionBundle, type PolicyConnector } from "./contracts.js";

export class StaleWholeBundleError extends Error {
  readonly code = "stale_state" as const;
  constructor(message = "a Snapshot-bound Read made the whole decision bundle stale") {
    super(message);
    this.name = "StaleWholeBundleError";
  }
}

export interface ConnectorPolicyClientOptions {
  productId?: string;
  productName?: string;
  productVersion?: string;
  clientInstanceId?: string;
}

type ActiveController = { session: ControllerSession };

export class ConnectorPolicyClient implements PolicyConnector {
  private capabilitiesValue?: Awaited<ReturnType<ConnectorAdapterClient["capabilities"]>>["data"];
  private controller?: ActiveController;
  private readonly options: Required<Pick<ConnectorPolicyClientOptions, "productId" | "productName" | "productVersion">> & Pick<ConnectorPolicyClientOptions, "clientInstanceId">;

  constructor(private readonly client: ConnectorAdapterClient, options: ConnectorPolicyClientOptions = {}) {
    this.options = {
      productId: options.productId ?? "sts2-policy-runtime",
      productName: options.productName ?? "STS2 Policy Runtime",
      productVersion: options.productVersion ?? POLICY_RUNTIME_VERSION,
      clientInstanceId: options.clientInstanceId
    };
  }

  async capabilities(options?: { fresh?: boolean }) {
    // A control precondition must observe the actual endpoint. Never overwrite
    // an admitted/cached identity merely because that endpoint was replaced.
    if (options?.fresh) return (await this.client.capabilities()).data;
    if (!this.capabilitiesValue) this.capabilitiesValue = (await this.client.capabilities()).data;
    return this.capabilitiesValue;
  }

  async observeBundle(requiredReadKinds: readonly string[]): Promise<DecisionBundle> {
    const observation = (await this.client.observe()).data;
    const required = new Set(requiredReadKinds);
    for (const kind of required) {
      if (!observation.reads.some((read) => read.kind === kind)) {
        throw new Error(`required_read_unavailable:${kind}`);
      }
    }
    try {
      return await prefetchPlayerEnvironmentDecisionBundle(
        observation,
        async (readId, expectedSnapshotId) => {
          try {
            return (await this.client.read(readId, expectedSnapshotId)).data;
          } catch (error) {
            if (isStale(error)) throw new StaleWholeBundleError(String(error));
            throw error;
          }
        },
        (read) => required.has(read.kind)
      );
    } catch (error) {
      if (error instanceof StaleWholeBundleError) throw error;
      throw error;
    }
  }

  async acquireController(): Promise<void> {
    if (this.controller) return;
    const capabilities = await this.capabilities();
    const session = new EnvironmentControllerSession(
      this.client as unknown as EnvironmentControlClient,
      {
        productId: this.options.productId,
        productName: this.options.productName,
        productVersion: this.options.productVersion,
        clientInstanceId: this.options.clientInstanceId
      }
    );
    await session.register(capabilities.host, capabilities.control);
    await session.credentials();
    this.controller = { session };
  }

  async releaseController(): Promise<void> {
    const active = this.controller;
    this.controller = undefined;
    if (active) await active.session.close();
  }

  async submit(input: { requestId: string; expectedSnapshotId: string; boundActionId: string }) {
    if (!this.controller) throw new Error("Policy Runtime requires an acquired Connector controller");
    const credentials = await this.controller.session.credentials();
    return (await this.client.submit({
      ...input,
      clientSessionId: credentials.clientSessionId,
      controllerLeaseId: credentials.controllerLeaseId,
      controllerGeneration: credentials.controllerGeneration
    })).data;
  }
}

function isStale(error: unknown): boolean {
  return error instanceof PlayerEnvironmentHttpError && error.statusCode === 409;
}
