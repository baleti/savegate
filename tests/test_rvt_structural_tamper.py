"""c4x-rvtgap 160-165: structural tampering of a gated 2026 family output (swap two FAT chain links, miniFAT link, redirect a stream start, stream size +-1, swapped names, truncation, appended byte) must be refused.
Documented benign exception: an appended all-zero sector is a spec-valid free sector, accepted (no data, no reference)."""
import os, sys, shutil, struct, tempfile, pytest
sys.path.insert(0, os.path.expanduser('~/rvt-research/write-lab')); sys.path.insert(0, os.path.expanduser('~/rvt-research'))
SRC = os.path.expanduser('~/rvt-research/samples-rfa/racbasicsamplefamily-2026.rfa')
pytestmark = pytest.mark.skipif(not os.path.exists(SRC), reason='no sample')

def test_structural_tampering_refused():
    import savegate as sg, wledit, cfb
    from savegate.adapters import RvtAdapter
    T = tempfile.mkdtemp()
    ed=wledit.Editor(SRC); PN=ed.trace(7)[0]; ed.set_strings([(7,'FillPattern.m_name','Flip')]); o=T+'/o.rfa'; ed.save(o)
    good=open(o,'rb').read(); c=cfb.CFB(good); ss=c.ss
    def off(sec): return (sec+1)*ss if ss==4096 else 512+sec*ss
    def run(pos):
        bad=good[:pos]+bytes([good[pos]^0x10])+good[pos+1:]
        cur=T+'/cur'; shutil.copy(SRC,cur); before=open(cur,'rb').read()
        doc=sg.open_doc(cur,RvtAdapter(),sg.Config(allow_overwrite=True,require_gate=False))
        try: sg.save(doc,bad,{'modified':['stream:'+PN,'el:7']}); return True
        except sg.SaveError: assert open(cur,'rb').read()==before; return False

    dbase=off(struct.unpack_from('<I',good,48)[0])
    def fatpos(sec):  # file offset of FAT entry for sector sec
        k=sec//(ss//4); fs=struct.unpack_from('<I',good,76+4*k)[0]; return off(fs)+4*(sec%(ss//4))
    def runb(bad):
        cur=T+'/cur'; shutil.copy(SRC,cur); before=open(cur,'rb').read()
        doc=sg.open_doc(cur,RvtAdapter(),sg.Config(allow_overwrite=True,require_gate=False))
        try: sg.save(doc,bad,{'modified':['stream:'+PN,'el:7']}); return True
        except sg.SaveError: assert open(cur,'rb').read()==before; return False
        except Exception as ex: return False
    def setb(b,pos,val): b=bytearray(b); b[pos:pos+len(val)]=val; return bytes(b)
    big=[(i,e) for i,e in enumerate(c.entries) if e.type==2 and e.size>=c.cutoff]
    small=[(i,e) for i,e in enumerate(c.entries) if e.type==2 and 0<e.size<c.cutoff]
    res={}
    # 160 swap two chain links of the first big stream with >=3 sectors
    for i,e in big:
        ch=[];x=e.start
        while x<0xFFFFFFF0: ch.append(x); x=c.fat[x]
        if len(ch)>=3:
            a,b=ch[0],ch[1]; pa,pb=fatpos(a),fatpos(b)
            va,vb=good[pa:pa+4],good[pb:pb+4]
            res['160 swap links '+e.name]=runb(setb(setb(good,pa,vb),pb,va)); break
    # 161 minifat
    mf=struct.unpack_from('<I',good,60)[0]
    for i,e in small:
        if e.size>64*2:
            m=e.start; nxt=struct.unpack_from('<I',good,off(mf)+4*m)[0]
            res['161 minifat link '+e.name]=runb(setb(good,off(mf)+4*m,struct.pack('<I',nxt+1 if nxt<0xFFFFFFF0 else 0)));break
    # 162 redirect start of a big stream to another big stream's start
    if len(big)>=2:
        (i1,e1),(i2,e2)=big[0],big[1]
        res['162 redirect start']=runb(setb(good,dbase+i1*128+116,struct.pack('<I',e2.start)))
    # 163 size +-1 big and small (raw dir size field)
    i1,e1=big[0]; res['163 big size+1']=runb(setb(good,dbase+i1*128+120,struct.pack('<Q',e1.size+1)))
    res['163 big size-1']=runb(setb(good,dbase+i1*128+120,struct.pack('<Q',e1.size-1)))
    i2,e2=small[0]; res['163 small size-1']=runb(setb(good,dbase+i2*128+120,struct.pack('<Q',e2.size-1)))
    # 164 swap names of two stream entries (name + len)
    (ia,ea),(ib,eb)=big[0],big[1]
    ra=good[dbase+ia*128:dbase+ia*128+66]; rb=good[dbase+ib*128:dbase+ib*128+66]
    res['164 swap names']=runb(setb(setb(good,dbase+ia*128,rb),dbase+ib*128,ra))
    # 165 truncate / append
    res['165 truncate 1 sector']=runb(good[:-ss])
    res['165 append zero sector']=runb(good+bytes(ss))
    res['165 append 1 byte']=runb(good+b'\0')
    acc = [k for k, v in res.items() if v and k != '165 append zero sector']
    assert not acc, acc
    assert len(res) >= 9

