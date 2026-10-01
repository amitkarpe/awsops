import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import yaml from "js-yaml";

const directory = new URL("./", import.meta.url);
const expected = new Map([
  ["s3-bucket-level-public-access-prohibited", "S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED"],
  ["s3-bucket-ssl-requests-only", "S3_BUCKET_SSL_REQUESTS_ONLY"],
  ["s3-bucket-server-side-encryption-enabled", "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED"],
  ["restricted-ssh", "INCOMING_SSH_DISABLED"],
  ["encrypted-volumes", "ENCRYPTED_VOLUMES"],
  ["ec2-ebs-encryption-by-default", "EC2_EBS_ENCRYPTION_BY_DEFAULT"],
]);
const aliases = ["lab-dev", "lab-poc", "lab-qa", "lab-sec"];

function fail(message) { throw Error(message); }
function keysEqual(value, keys) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).sort().join(",") === [...keys].sort().join(",");
}
function unique(values) { return new Set(values).size === values.length; }

export function validate(manifest, templateText, liveRegistry) {
  if (!keysEqual(manifest, ["schemaVersion", "packName", "packVersion", "region", "aliases", "liveRegistryVersion", "controls"]) ||
      manifest.schemaVersion !== 1 || manifest.packVersion !== 1 ||
      manifest.packName !== "awsops-home-readonly-v1" || manifest.region !== "ap-southeast-1" ||
      JSON.stringify(manifest.aliases) !== JSON.stringify(aliases) || manifest.liveRegistryVersion !== 1)
    fail("pack identity or scope mismatch");
  if (!Array.isArray(manifest.controls) || manifest.controls.length !== expected.size)
    fail("exact six-control inventory required");
  const ids = manifest.controls.map((control) => control?.id);
  const sourceIds = manifest.controls.map((control) => control?.sourceIdentifier);
  const ruleNames = manifest.controls.map((control) => control?.ruleName);
  const logicalIds = manifest.controls.map((control) => control?.logicalId);
  if (!unique(ids) || !unique(sourceIds) || !unique(ruleNames) || !unique(logicalIds) ||
      [...expected.keys()].some((id) => !ids.includes(id))) fail("duplicate or missing control");
  for (const control of manifest.controls) {
    if (!keysEqual(control, ["id", "logicalId", "ruleName", "sourceIdentifier", "state", "documentation"]) ||
        expected.get(control.id) !== control.sourceIdentifier ||
        !/^[A-Z][A-Za-z0-9]{1,80}$/.test(control.logicalId) ||
        !/^awsops-v1-[a-z0-9-]{3,70}$/.test(control.ruleName) ||
        !["accepted", "planned"].includes(control.state) ||
        control.documentation !== `https://docs.aws.amazon.com/config/latest/developerguide/${control.id}.html`)
      fail("unapproved control metadata");
  }
  if (!liveRegistry || liveRegistry.version !== 1 || liveRegistry.region !== manifest.region ||
      JSON.stringify(liveRegistry.aliases) !== JSON.stringify(aliases) ||
      !Array.isArray(liveRegistry.controls) || liveRegistry.controls.length !== 2)
    fail("live registry mismatch");
  const live = new Map(liveRegistry.controls.map((control) => [control.id, control.sourceIdentifier]));
  const accepted = manifest.controls.filter((control) => control.state === "accepted");
  if (accepted.length !== 2 || live.size !== 2 ||
      accepted.some((control) => live.get(control.id) !== control.sourceIdentifier))
    fail("accepted controls drift from live registry");
  if (typeof templateText !== "string" || Buffer.byteLength(templateText) > 51200)
    fail("invalid template size");
  let template;
  try { template = yaml.load(templateText); } catch { fail("invalid or duplicate YAML"); }
  if (!keysEqual(template, ["Resources"]) || !keysEqual(template.Resources, logicalIds))
    fail("template must contain exactly six fixed Config rules");
  for (const control of manifest.controls) {
    const resource = template.Resources[control.logicalId];
    if (!keysEqual(resource, ["Type", "Properties"]) || resource.Type !== "AWS::Config::ConfigRule" ||
        !keysEqual(resource.Properties, ["ConfigRuleName", "Source"]) ||
        resource.Properties.ConfigRuleName !== control.ruleName ||
        !keysEqual(resource.Properties.Source, ["Owner", "SourceIdentifier"]) ||
        resource.Properties.Source.Owner !== "AWS" ||
        resource.Properties.Source.SourceIdentifier !== control.sourceIdentifier)
      fail("template contains an unapproved rule, parameter or action");
  }
  return { pack: manifest.packName, version: manifest.packVersion, controls: expected.size,
    accepted: accepted.length, planned: expected.size - accepted.length, aliases: aliases.length,
    remediation: false };
}

export function validateFiles() {
  const manifest = JSON.parse(readFileSync(new URL("manifest.v1.json", directory), "utf8"));
  const template = readFileSync(new URL("awsops-home-readonly-v1.yaml", directory), "utf8");
  const live = JSON.parse(readFileSync(new URL("../control-registry.json", directory), "utf8"));
  return validate(manifest, template, live);
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  try {
    const result = validateFiles();
    console.log(`CONFIG_PACK_VALIDATION_OK controls=${result.controls} accepted=${result.accepted} planned=${result.planned} aliases=${result.aliases} remediation=false`);
  } catch (error) {
    console.error(`CONFIG_PACK_VALIDATION_FAIL ${error.message}`);
    process.exitCode = 1;
  }
}
