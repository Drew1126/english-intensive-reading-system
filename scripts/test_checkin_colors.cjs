const fs=require('fs'),vm=require('vm'),assert=require('assert');
const context={document:{createElement:()=>({style:{}})}};
vm.createContext(context);vm.runInContext(fs.readFileSync('frontend/js/checkin.js','utf8'),context);
let previous=101;
for(let count=1;count<=10;count++){
    const badge=context.checkinModule.badge(count);
    const light=Number(badge.style.backgroundColor.match(/, (\d+)%\)$/)[1]);
    assert(light<previous);previous=light;
    assert(badge.textContent.includes(String(count)));
}
console.log('PASS: check-in count labels and progressively darker colors');
