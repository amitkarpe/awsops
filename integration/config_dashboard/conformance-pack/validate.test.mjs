import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { validate } from "./validate.mjs";

const manifest = JSON.parse(readFileSync(new URL("./manifest.v1.json", import.meta.url), "utf8"));
const template = readFileSync(new URL("./awsops-home-readonly-v1.yaml", import.meta.url), "utf8");
const live = JSON.parse(readFileSync(new URL("../control-registry.json", import.meta.url), "utf8"));
const copy = (value) => structuredClone(value);

test("six fixed AWS managed rules match the two-control live registry", () => {
  assert.deepEqual(validate(manifest, template, live), {
    pack: "awsops-home-readonly-v1", version: 1, controls: 6,
    accepted: 2, planned: 4, aliases: 4, remediation: false,
  });
});

test("duplicate, missing, or changed controls fail closed", () => {
  const duplicate = copy(manifest);
  duplicate.controls[1] = copy(duplicate.controls[0]);
  assert.throws(() => validate(duplicate, template, live), /duplicate or missing control/);
  const changed = copy(manifest);
  changed.controls[1].sourceIdentifier = "MODEL_SELECTED_RULE";
  assert.throws(() => validate(changed, template, live), /unapproved control metadata/);
  const drift = copy(live);
  drift.controls.pop();
  assert.throws(() => validate(manifest, template, drift), /live registry mismatch/);
});

test("remediation, extra resources, parameters, and duplicate YAML keys fail closed", () => {
  const remediation = template.replace("Type: AWS::Config::ConfigRule", "Type: AWS::Config::RemediationConfiguration");
  assert.throws(() => validate(manifest, remediation, live), /unapproved rule/);
  const extra = `${template}\n  ArbitraryAction:\n    Type: AWS::Config::RemediationConfiguration\n`;
  assert.throws(() => validate(manifest, extra, live), /exactly six fixed Config rules/);
  const parameter = template.replace("      Source:\n", "      InputParameters:\n        resourceId: user-selected\n      Source:\n");
  assert.throws(() => validate(manifest, parameter, live), /unapproved rule/);
  assert.throws(() => validate(manifest, `${template}\nResources: {}\n`, live), /invalid or duplicate YAML/);
});
