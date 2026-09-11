// Read-only source AST account of the exact C10 runner witness, not runner trust.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const root=process.cwd(),base='fc823071a7b6f2c9a573172aec3499ad6d138c0f';
const file='apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.ts';
execFileSync('git',['diff','--exit-code',base,'--',file],{cwd:root});
const require=createRequire(path.join(root,'apps/runtime-dashboard/package.json'));
const ts=require('typescript'), text=fs.readFileSync(file,'utf8');
const tree=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TS);
const a=[],b=[],functions=[],calls=[];
const wanted=n=>ts.isFunctionDeclaration(n)||ts.isCallExpression(n)||ts.isNewExpression(n);
const key=n=>`${n.kind}:${n.pos}:${n.end}`;
function first(n){if(wanted(n))a.push(key(n));if(ts.isFunctionDeclaration(n))functions.push(n.name?.text);if(ts.isCallExpression(n))calls.push({line:tree.getLineAndCharacterOfPosition(n.getStart(tree)).line+1,name:n.expression.getText(tree)});ts.forEachChild(n,first)}
function second(n){if(wanted(n))b.push(key(n));for(const c of n.getChildren(tree))second(c)}
first(tree);second(tree);
if(JSON.stringify(a.sort())!==JSON.stringify(b.sort()))throw Error('AST disagreement');
const fields=[];
function find(n){if(ts.isObjectLiteralExpression(n)) {const names=n.properties.map(p=>p.name?.getText(tree));if(names.includes('sha256')&&names.includes('version'))fields.push({line:tree.getLineAndCharacterOfPosition(n.getStart(tree)).line+1,names,expressions:n.properties.map(p=>p.getText(tree))});}ts.forEachChild(n,find)}
find(tree);
const captured=tree.statements.filter(n=>ts.isVariableStatement(n)&&n.getText(tree).includes('attests intake closure')).map(n=>n.getText(tree));
console.log(JSON.stringify({base,file,denominator:'all nodes of this one .ts owner file',parse_errors:tree.parseDiagnostics.map(d=>ts.flattenDiagnosticMessageText(d.messageText,'\n')),independent_node_sets_equal:true,functions,calls,runner_identity_object_population:fields,intake_scope:captured,live_out_of_band_runner_identity_established:false},null,2));
