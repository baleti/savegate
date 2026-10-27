import sys, os, time; sys.path[:0]=['~/src/savegate','~/rvt-research/write-lab']
import savegate as sg, cfb
from savegate.adapters import RvtAdapter
from savegate.rvt_elements import elements
f='~/rvt-research/write-lab/scenes/classtests/2024_writer_cols2.rte'
buf=open(f,'rb').read(); t=time.time(); e=elements(buf); print(len(e),'elements',round(time.time()-t,1),'s')
cfb.write(cfb.CFB(buf),'/tmp/sg_same_h1.rte'); e2=elements(open('/tmp/sg_same_h1.rte','rb').read()); print('identity relayout equal:', e==e2)
