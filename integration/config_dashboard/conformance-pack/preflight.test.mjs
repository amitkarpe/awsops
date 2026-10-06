import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { test } from "node:test";
import { preparePlan, preflight } from "./preflight.mjs";

import { syntheticPreflight } from "./preflight.synthetic.mjs";

const run = ({ expected, plan, approval, facts, now }) => preflight(expected, plan, approval, facts, now);

test("plan binds source bytes and one target; create/no-op stay synthetic and non-executable", () => {
  const f = syntheticPreflight();
  const template = readFileSync(new URL("awsops-home-readonly-v1.yaml", import.meta.url));
  assert.equal(f.plan.source.templateSha256, createHash("sha256").update(template).digest("hex"));
  assert.ok(Object.isFrozen(f.plan) && Object.isFrozen(f.plan.target) && Object.isFrozen(f.plan.controls));
  assert.throws(() => { f.plan.target.alias = "lab-qa"; }, TypeError);
  assert.equal(f.plan.proposedApi, "config:PutConformancePack");
  assert.equal(f.plan.operation, "CREATE");
  assert.equal(f.plan.controls.length, 6);
  assert.equal(run(f).disposition, "CREATE_CANDIDATE");
  for (const alias of ["lab-dev", "lab-poc", "lab-qa", "lab-sec"]) {
    const expected = structuredClone(f.expected); expected.target.alias = alias;
    const plan = preparePlan(expected);
    assert.equal(plan.target.alias, alias);
    if (alias !== "lab-dev") assert.notEqual(plan.planDigest, f.plan.planDigest);
  }
  f.facts.pack.state = "STABLE";
  f.facts.pack.templateSha256 = f.plan.source.templateSha256;
  assert.deepEqual(run(f), { schemaVersion: 1, status: "OFFLINE_PREFLIGHT_VALID", evidenceKind: "SYNTHETIC_ONLY",
    disposition: "NOOP_CANDIDATE", executionAllowed: false, liveApproval: "NOT_VERIFIED",
    liveReadiness: "NOT_VERIFIED", awsCalls: 0 });
  assert.doesNotMatch(JSON.stringify(run(f)), /111111111111|AROA|synthetic-pack-role|planDigest/);
});

test("edited operations, targets, source, controls and extra fields cannot reuse a plan", () => {
  for (const mutate of [
    p => { p.operation = "UPDATE"; }, p => { p.proposedApi = "config:PutOrganizationConformancePack"; },
    p => { p.target.alias = "lab-qa"; }, p => { p.target.accountId = "2".repeat(12); },
    p => { p.target.roleId = "AROA" + "B".repeat(17); }, p => { p.region = "us-east-1"; },
    p => { p.source.commit = "b".repeat(40); }, p => { p.source.templateSha256 = "b".repeat(64); },
    p => { p.source.gatePacketSha256 = "b".repeat(64); }, p => { p.controls.pop(); },
    p => { p.constraints.executionAllowed = true; }, p => { p.planDigest = "b".repeat(64); },
    p => { p.endpoint = "private-value"; }, p => { p.source.extra = undefined; }, p => { delete p.source; },
  ]) {
    const f = syntheticPreflight(); f.plan = structuredClone(f.plan); mutate(f.plan);
    assert.throws(() => run(f), /^Error: CONFIG_PACK_PREFLIGHT_REJECTED$/);
  }
  for (const target of [null, {}, { alias: "prod" }, { ...syntheticPreflight().expected.target, accountId: "<ACCOUNT>" }]) {
    assert.throws(() => preparePlan({ sourceCommit: "a".repeat(40), target }), /CONFIG_PACK_PREFLIGHT_REJECTED/);
  }
  const f = syntheticPreflight(); f.expected.sourceCommit = "b".repeat(40);
  assert.throws(() => run(f), /CONFIG_PACK_PREFLIGHT_REJECTED/);
});

test("missing, stale, future, mismatched or purported live approvals fail closed", () => {
  for (const mutate of [
    f => { f.approval = null; }, f => { f.approval.planDigest = "b".repeat(64); },
    f => { f.approval.decision = "APPROVED"; }, f => { f.approval.evidenceKind = "LIVE"; },
    f => { f.approval.expiresAt = f.now; }, f => { f.approval.issuedAt = f.now + 1; },
    f => { f.approval.expiresAt = f.now + 300001; }, f => { f.approval.issuedAt = true; },
    f => { f.approval.private = "not-for-logs"; }, f => { f.now = NaN; },
    ...Object.keys(syntheticPreflight().approval.gates).flatMap(gate => [
      f => { delete f.approval.gates[gate]; }, f => { f.approval.gates[gate] = false; },
      f => { f.approval.gates[gate] = "true"; },
    ]),
  ]) { const f = syntheticPreflight(); mutate(f); assert.throws(() => run(f), /^Error: CONFIG_PACK_PREFLIGHT_REJECTED$/); }
});

test("missing or inconsistent target facts, prerequisites and pack state fail closed", () => {
  for (const mutate of [
    f => { f.facts = null; }, f => { f.facts.target.alias = "lab-poc"; },
    f => { f.facts.target.accountId = "2".repeat(12); }, f => { f.facts.target.roleName += "-other"; },
    f => { f.facts.target.roleId = "AROA" + "B".repeat(17); }, f => { f.facts.region = "us-east-1"; },
    f => { f.facts.planDigest = "b".repeat(64); }, f => { f.facts.evidenceKind = "LIVE"; },
    f => { f.facts.observedAt = f.now - 300001; }, f => { f.facts.observedAt = f.now + 1; },
    f => { f.facts.recorderActive = false; }, f => { f.facts.conformsRoleExists = false; },
    f => { f.facts.pack.name = "other"; }, f => { f.facts.pack.state = "UNKNOWN"; },
    f => { f.facts.pack.state = "IN_PROGRESS"; }, f => { f.facts.pack.templateSha256 = "b".repeat(64); },
    f => { f.facts.pack = { name: f.plan.packName, state: "STABLE", templateSha256: "b".repeat(64) }; },
    f => { f.facts.nextToken = "private-pagination"; }, f => { delete f.facts.recorderActive; },
  ]) { const f = syntheticPreflight(); mutate(f); assert.throws(() => run(f), /^Error: CONFIG_PACK_PREFLIGHT_REJECTED$/); }
});
