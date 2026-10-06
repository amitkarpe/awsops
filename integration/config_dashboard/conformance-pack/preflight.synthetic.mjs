// Invented in-memory inputs only; never owner approval or provider evidence.
import { preparePlan } from "./preflight.mjs";

export function syntheticPreflight(sourceCommit = "a".repeat(40)) {
  const expected = { sourceCommit, target: { alias: "lab-dev", accountId: "1".repeat(12),
    roleName: "synthetic-pack-role", roleId: "AROA" + "A".repeat(17) } };
  const plan = preparePlan(expected);
  const now = 2000000;
  const approval = { schemaVersion: 1, evidenceKind: "SYNTHETIC_ONLY", decision: "APPROVE_OFFLINE_REHEARSAL",
    planDigest: plan.planDigest, issuedAt: now - 1000, expiresAt: now + 1000,
    gates: { target: true, pack: true, controls: true, actions: true,
      rollbackRetention: true, cost: true, exclusions: true } };
  const facts = { schemaVersion: 1, evidenceKind: "SYNTHETIC_ONLY", planDigest: plan.planDigest,
    observedAt: now, target: structuredClone(expected.target), region: "ap-southeast-1",
    recorderActive: true, conformsRoleExists: true,
    pack: { name: plan.packName, state: "ABSENT", templateSha256: null } };
  return { expected, plan, approval, facts, now };
}
