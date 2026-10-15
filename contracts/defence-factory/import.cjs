#!/usr/bin/env node
'use strict';
// Bounded stdin only: never reads credentials, invokes AWS, or echoes rejected input.
const {intake,MAX_BYTES}=require('./intake.cjs');const chunks=[];let size=0,failed=false;
function fail(){if(failed)return;failed=true;process.stderr.write('INVALID_SYNTHETIC_INPUT\n');process.exitCode=1;process.stdin.destroy();}
if(!['json','csv'].includes(process.argv[2])||process.argv.length!==3)fail();
process.stdin.on('data',chunk=>{size+=chunk.length;if(size>MAX_BYTES)fail();else if(!failed)chunks.push(chunk);});
process.stdin.on('end',()=>{if(failed)return;try{const result=intake(new Uint8Array(Buffer.concat(chunks)),process.argv[2]);process.stdout.write(JSON.stringify(result)+'\n');}catch{fail();}});process.stdin.on('error',fail);
