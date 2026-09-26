'use strict';
// One separately reviewed manual-canary baseline. The release profile is unchanged.
const base = require('../librechat/rehearse_patch.cjs');
const pin = require('./upstream.json');
const STAGE_MARKER = '    this.stagedApproval = {\n      streamId,';
const MANUAL = `      if (req._isScheduledFire || req._agentEventBindingId ||
          job.metadata?.scheduleId || job.metadata?.agentEventSuspension ||
          job.metadata?.agentEventInvocationKey || job.metadata?.agentEventDeliveryKey) {
        throw Error('AWSOPS_MANUAL_CANARY_ONLY');
      }
`;
const PRE = base.PRE.replace('      awsopsNativeEnvelope =', MANUAL + '      awsopsNativeEnvelope =');
const PAUSE = base.PAUSE.replace('      await require(', `      if (this.eventActorInvocationId || this.options.req?._isScheduledFire ||
          this.options.req?._agentEventBindingId) throw Error('AWSOPS_MANUAL_CANARY_ONLY');
      await require(`);
function render(raw, component) {
  if (!['resume', 'pause'].includes(component)) throw Error('INVALID_CANARY_COMPONENT');
  const expected = component === 'resume' ? pin.controller_blob : pin.producer_blob;
  if (base.blob(raw) !== expected) throw Error('CANARY_SOURCE_DRIFT');
  let source = raw.toString('utf8');
  const pairs = component === 'resume' ? [[base.PRE_MARKER, PRE], [base.POST_MARKER, base.POST]] : [[STAGE_MARKER, PAUSE]];
  for (const [marker, insert] of pairs) {
    if (source.split(marker).length !== 2) throw Error('CANARY_SEAM_DRIFT');
    source = source.replace(marker, insert + marker);
  }
  return Buffer.from(source);
}
module.exports = {pin, render, PRE, PAUSE, MANUAL, STAGE_MARKER};
