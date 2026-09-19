"""Describe discount auth/tariff dataflow from an offline JADX directory.

No network calls, account data or credential values. Only selected structural
lines are emitted; all string literals are redacted except field/protocol names.
"""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

SAFE={'','Basic ','Bearer ','Authorization','tariff_id','rubric_id','id','name'}
STRINGS=re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')


def sanitized(line):
    return STRINGS.sub(lambda m:m[0] if m[1] in SAFE else '"[literal omitted]"',line.strip())


def method_lines(lines,needle):
    starts=[n for n,s in enumerate(lines) if needle in s and re.search(r'\b(?:public|private|protected)\b',s)
            and '(' in s and '{' in s and not s.lstrip().startswith('@')]
    result=[]
    for start in starts:
        depth=0
        for n in range(start,min(start+65,len(lines))):
            line=lines[n];clean=sanitized(line)
            result.append({'line':n+1,'structure':clean})
            depth+=clean.count('{')-clean.count('}')
            if n>start and depth<=0:break
    return result


def main(root):
    result={'input_type':'signed_public_apk_decompilation','source_account_access':False,
            'network_calls':0,'credential_literals_exported':False,'files':[]}
    rules={'BaseAuthHelper.java':['getBenefitsHeaderForAuth'],
           'StorageRepositoryImpl.java':['getTariff'],
           'Tariff.java':['getId','getTariffId'],
           'BenefitsFragment.java':[], 'IContract.java':[], 'BuildConfig.java':[]}
    for f in root.rglob('*.java'):
        if f.name not in rules or '/com/konsierge/' not in str(f):continue
        s=f.read_text(errors='replace');lines=s.splitlines();selected=[]
        for name in rules[f.name]:selected+=method_lines(lines,name)
        if f.name=='BenefitsFragment.java':
            # The already observed call site, including id extraction after getTariff.
            for n,line in enumerate(lines):
                if '.getTariff()' in line:
                    selected += [{'line':i+1,'structure':sanitized(lines[i])} for i in range(max(0,n-3),min(len(lines),n+19))]
        if f.name=='IContract.java':
            selected=[{'line':n+1,'structure':sanitized(line)} for n,line in enumerate(lines)
                      if re.search(r'\b(?:TARIFF_ID|RUBRIC_ID)\s*=',line)]
        if f.name=='BuildConfig.java':
            selected=[{'line':n+1,'structure':sanitized(line)} for n,line in enumerate(lines)
                      if re.search(r'\b[A-Z_]*(?:BENEFIT|TARIFF)[A-Z_]*\s*=',line)]
        if selected:
            result['files'].append({'file':str(f.relative_to(root)),'sha256':hashlib.sha256(s.encode()).hexdigest(),'lines':selected})
    out=Path('only-assist-evidence');out.mkdir(exist_ok=True)
    (out/'auth_origin_structure.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('Sanitized structural files:',len(result['files']))


if __name__=='__main__':
    assert sanitized('String x = "do-not-export-secret-123";')=='String x = "[literal omitted]";'
    assert sanitized('return "Basic " + value;')=='return "Basic " + value;'
    main(Path(sys.argv[1]))
