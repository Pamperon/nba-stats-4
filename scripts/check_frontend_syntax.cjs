/* Include every browser module in syntax checks, including future extractions. */
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
function check(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,entry.name);if(entry.isDirectory())check(file);else if(file.endsWith('.js'))cp.execFileSync(process.execPath,['--check',file],{stdio:'inherit'});}}
check('web');
