'use strict';
// LibreChat toolApproval hook loader expects the module default export to be a builder.
module.exports = require('../librechat/pause_gate.cjs').approvalHook;
