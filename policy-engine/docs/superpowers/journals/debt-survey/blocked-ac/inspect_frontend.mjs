// Read-only TypeScript AST census at the pinned source base; not a flow proof.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import crypto from 'node:crypto';

const root = process.cwd();
const base = 'fc823071a7b6f2c9a573172aec3499ad6d138c0f';
const require = createRequire(path.join(root, 'apps/runtime-dashboard/package.json'));
const ts = require('typescript');
const paths = execFileSync('git', ['ls-tree', '-r', '--name-only', base, '--', 'apps', 'packages'], {cwd:root, encoding:'utf8'})
  .trim().split('\n').filter(x => /\.tsx?$/.test(x)).sort();
const tracked = new Set(execFileSync('git', ['ls-files', '-z', '--', 'apps', 'packages'], {cwd:root, encoding:'utf8'}).split('\0'));
const walked = [];
function walk(dir) {
  for (const item of fs.readdirSync(path.join(root,dir),{withFileTypes:true})) {
    const next=path.posix.join(dir,item.name);
    if (item.isDirectory() && !['node_modules','.next','dist','build','.turbo','test-results','playwright-report'].includes(item.name)) walk(next);
    else if (item.isFile() && /\.tsx?$/.test(next) && tracked.has(next)) walked.push(next);
  }
}
walk('apps'); walk('packages'); walked.sort();
if(JSON.stringify(paths)!==JSON.stringify(walked)) throw new Error('Pinned Git and independent filesystem denominator differ');
execFileSync('git',['diff','--exit-code',base,'--','apps','packages'],{cwd:root});
const trackedKinds = new Set([ts.SyntaxKind.FunctionDeclaration,ts.SyntaxKind.FunctionExpression,ts.SyntaxKind.ArrowFunction,
ts.SyntaxKind.ClassDeclaration,ts.SyntaxKind.MethodDeclaration,ts.SyntaxKind.TypeAliasDeclaration,ts.SyntaxKind.InterfaceDeclaration,
ts.SyntaxKind.CallExpression,ts.SyntaxKind.NewExpression]);
const query = /PromptToolParserAuthorityLedger|CompressionLossReceipt|agent_session|orchestration_audit|ProjectionFreshness|[Pp]ublic.*(Verification|[Ii]ntegrity|Presentation)|[Pp]romotion.*Presentation|[Bb]locker.*Presentation/;
const selected=[], clerk=[], failures=[], distribution={};
for(const file of paths) {
  const text=fs.readFileSync(path.join(root,file),'utf8');
  const source=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,file.endsWith('.tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
  failures.push(...source.parseDiagnostics.map(x=>({file,message:ts.flattenDiagnosticMessageText(x.messageText,'\n')})));
  const key=n=>`${n.kind}:${n.getStart(source)}:${n.end}`;
  const a=[],b=[],nodes=[];
  function first(n){if(trackedKinds.has(n.kind)){a.push(key(n));nodes.push(n)}ts.forEachChild(n,first)}
  function second(n){if(trackedKinds.has(n.kind))b.push(key(n));for(const child of n.getChildren(source))second(child)}
  first(source);second(source);
  if(JSON.stringify(a.sort())!==JSON.stringify(b.sort()))throw new Error(`AST derivations differ: ${file}`);
  const group=file.split('/').slice(0,2).join('/');
  distribution[group]??={files:0,definitions:0,calls:0};distribution[group].files++;
  for(const n of nodes) {
    const call=ts.isCallExpression(n)||ts.isNewExpression(n);
    distribution[group][call?'calls':'definitions']++;
    const name=call?n.expression.getText(source):n.name?.getText(source)||n.parent?.name?.getText(source)||'<anonymous>';
    const row={file,kind:ts.SyntaxKind[n.kind],line:source.getLineAndCharacterOfPosition(n.getStart(source)).line+1,name};
    if(file.startsWith('apps/runtime-dashboard/src/features/clerk/'))clerk.push(row);
    if(query.test(name)||(!call&&query.test(n.getText(source))&&file.includes('cacheAgePresentation')))selected.push(row);
  }
}
const clerkPaths=paths.filter(x=>x.startsWith('apps/runtime-dashboard/src/features/clerk/'));
const clerkliterals=clerkPaths.flatMap(file=>fs.readFileSync(path.join(root,file),'utf8').split('\n').flatMap((line,i)=>/PromptToolParserAuthorityLedger|CompressionLossReceipt|agent_session|orchestration_audit/.test(line)?[{file,line:i+1,text:line}]:[]));
console.log(JSON.stringify({base,file_type:'.ts/.tsx including tests and declarations',path_denominator:'apps/** and packages/**',
files:paths.length,path_sha256:crypto.createHash('sha256').update(paths.join('\n')).digest('hex'),
path_identity_crosscheck:'pinned git ls-tree == independent filesystem walk intersect current tracked set',
node_identity_crosscheck:'forEachChild == recursive getChildren for every selected definition/call node',
parse_failures:failures,distribution,query:query.source,matches:selected,clerk:{files:clerkPaths.length,paths:clerkPaths,
definitions_and_calls:clerk,literal_query:'PromptToolParserAuthorityLedger|CompressionLossReceipt|agent_session|orchestration_audit',literal_matches:clerkliterals}},null,2));
