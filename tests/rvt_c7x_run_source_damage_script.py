import os,sys,random,shutil
sys.path.insert(0,os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0,os.path.expanduser('~/rvt-research')); sys.path.insert(0,os.environ['SGPKG'])
from savegate import rvt_writer_ops as WO
S=os.path.expanduser('~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt'); os.makedirs('w437',exist_ok=True)
k=sys.argv[1]; src=S
if k=='flips':
    b=bytearray(open(S,'rb').read()); random.seed(int(sys.argv[2]) if len(sys.argv)>2 else 437)
    for _ in range(int(sys.argv[3]) if len(sys.argv)>3 else 1): b[random.randrange(len(b)//4,len(b))]^=0x55
    src='w437/damaged.rvt'; open(src,'wb').write(b)
try: WO.run(src,[{'op':'move_textnote','id':916133,'dx':1.0}],'w437/o.rvt'); r='ACCEPTED'
except Exception as e: r='REFUSED'
print('T437',k,r); sys.exit(0 if (r=='ACCEPTED')==(k=='clean') else 1)
