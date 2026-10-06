// Versioned offline schema and consistency checks only. No provider or executor.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { validate } from "./validate.mjs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const reject = () => { throw Error("CONFIG_PACK_PREFLIGHT_REJECTED"); };
const requireThat = (condition) => { if (!condition) reject(); };
const keys = (value, expected) => requireThat(value && typeof value === "object" &&
  !Array.isArray(value) && Object.keys(value).sort().join(",") === [...expected].sort().join(","));
const matches = (value, pattern) => typeof value === "string" && pattern.test(value);
const canonical = (value) => JSON.stringify(value, function (_key, item) {
  return item && typeof item === "object" && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]])) : item;
});
const hash = (value) => createHash("sha256").update(value).digest("hex");
const digest = (value) => hash(canonical(value));
const freeze = (value) => {
  for (const item of Object.values(value)) if (item && typeof item === "object") freeze(item);
  return Object.freeze(value);
};
const gates = ["target", "pack", "controls", "actions", "rollbackRetention", "cost", "exclusions"];

function targetShape(target, aliases) {
  keys(target, ["alias", "accountId", "roleName", "roleId"]);
  requireThat(aliases.includes(target.alias) && matches(target.accountId, /^\d{12}$/) &&
    matches(target.roleName, /^[\w+=,.@-]{1,64}$/) && matches(target.roleId, /^AROA[A-Z0-9]{17}$/));
}

// expected is independent caller-owned context, never taken from the submitted
// plan/approval/facts. It is NOT authenticated by this offline module.
export function preparePlan(expected) {
  try {
    keys(expected, ["sourceCommit", "target"]);
    requireThat(matches(expected.sourceCommit, /^[a-f0-9]{40}$/));
    const manifestText = read("manifest.v1.json");
    const templateText = read("awsops-home-readonly-v1.yaml");
    const registryText = read("../control-registry.json");
    const manifest = JSON.parse(manifestText);
    validate(manifest, templateText, JSON.parse(registryText));
    targetShape(expected.target, manifest.aliases);
    const body = {
      schemaVersion: 1, mode: "OFFLINE_ONLY", operation: "CREATE",
      proposedApi: "config:PutConformancePack", region: manifest.region,
      packName: manifest.packName, packVersion: manifest.packVersion,
      target: { ...expected.target },
      source: { commit: expected.sourceCommit, templateSha256: hash(templateText),
        manifestSha256: hash(manifestText), registrySha256: hash(registryText),
        gatePacketSha256: hash(read("../../../docs/current/CONFIG_PACK_M4.md")) },
      controls: manifest.controls.map((control) => control.sourceIdentifier),
      gateIssues: [62, 70, 77],
      constraints: { stages: 1, updateAllowed: false, deletionAllowed: false,
        remediationAllowed: false, executionAllowed: false },
    };
    return freeze({ ...body, planDigest: digest(body) });
  } catch { reject(); }
}

// Strict schemas reject extra fields too. APPROVE_OFFLINE_REHEARSAL and the
// seven simulated attestations can prove consistency only, never owner consent.
export function preflight(expected, plan, approval, facts, now) {
  try {
    const wanted = preparePlan(expected);
    requireThat(isDeepStrictEqual(plan, wanted));
    requireThat(Number.isSafeInteger(now) && now >= 0);
    keys(approval, ["schemaVersion", "evidenceKind", "decision", "planDigest", "issuedAt", "expiresAt", "gates"]);
    requireThat(approval.schemaVersion === 1 && approval.evidenceKind === "SYNTHETIC_ONLY" &&
      approval.decision === "APPROVE_OFFLINE_REHEARSAL" && approval.planDigest === wanted.planDigest &&
      Number.isSafeInteger(approval.issuedAt) && approval.issuedAt >= 0 && approval.issuedAt <= now &&
      Number.isSafeInteger(approval.expiresAt) && now < approval.expiresAt &&
      approval.expiresAt - approval.issuedAt <= 300000);
    keys(approval.gates, gates);
    requireThat(gates.every((gate) => approval.gates[gate] === true));
    keys(facts, ["schemaVersion", "evidenceKind", "planDigest", "observedAt", "target", "region",
      "recorderActive", "conformsRoleExists", "pack"]);
    requireThat(facts.schemaVersion === 1 && facts.evidenceKind === "SYNTHETIC_ONLY" &&
      facts.planDigest === wanted.planDigest && isDeepStrictEqual(facts.target, wanted.target) &&
      facts.region === wanted.region && facts.recorderActive === true && facts.conformsRoleExists === true &&
      Number.isSafeInteger(facts.observedAt) && facts.observedAt >= approval.issuedAt &&
      facts.observedAt <= now && now - facts.observedAt <= 300000);
    keys(facts.pack, ["name", "state", "templateSha256"]);
    requireThat(facts.pack.name === wanted.packName);
    let disposition;
    if (facts.pack.state === "ABSENT" && facts.pack.templateSha256 === null) {
      disposition = "CREATE_CANDIDATE";
    } else if (facts.pack.state === "STABLE" && facts.pack.templateSha256 === wanted.source.templateSha256) {
      disposition = "NOOP_CANDIDATE";
    } else reject(); // Unknown, partial, in-progress or divergent is never an update.
    // Fixed public projection: no input values or hashes of private bindings.
    return Object.freeze({ schemaVersion: 1, status: "OFFLINE_PREFLIGHT_VALID",
      evidenceKind: "SYNTHETIC_ONLY", disposition, executionAllowed: false,
      liveApproval: "NOT_VERIFIED", liveReadiness: "NOT_VERIFIED", awsCalls: 0 });
  } catch { reject(); }
}
