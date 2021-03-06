import sys,logging,base64
from sqlalchemy import *
from sqlalchemy import exc

from sqlalchemy import MetaData, Table, Column, Integer
import binascii
from ConfigParser import SafeConfigParser
import pandas as pd
import collections
import numpy as np
from collections import Counter
from datetime import datetime
from brilws import api
import time
import array
import re
from sqlalchemy import schema, types
dbtimefm = 'MM/DD/YY HH24:MI:SS.ff6'
pydatetimefm = '%m/%d/%y %H:%M:%S.%f'

def getshardid(connection,runnum):
    q = '''select id from TABLESHARDS where MINRUN<:runnum and MAXRUN>:runnum'''
    shardid = None
    with connection.begin() as trans:
        row = connection.execute(q,{'runnum':runnum}).fetchone()
        if row:
            shardid = row['id']
    return shardid

def unpack64to32(a):
    b = a & 0xffffffff
    c = a >> 32
    return (b,c)
    
def unpackblobstr(iblobstr,itemtypecode):
    if itemtypecode not in ['c','b','B','u','h','H','i','I','l','L','f','d']:
        raise RuntimeError('unsupported typecode '+itemtypecode)
    result=array.array(itemtypecode)
    #blobstr=iblob.readline()
    if not iblobstr :
        return result
    result.fromstring(iblobstr)
    return result


def datatagid_of_run(connection,runnum,datatagnameid=0):
    qid = '''select datatagid as datatagid from ids_datatag where datatagnameid=:datatagnameid and runnum=:runnum and lsnum=1'''
    myid = 0
    with connection.begin() as trans:
        row = connection.execute(qid,{'datatagnameid':datatagnameid,'runnum':runnum}).fetchone()
        if row:
            myid = row['datatagid']
    return myid

def datatagid_of_ls(connection,runnum,datatagnameid=0):
    '''
    output: {lsnum:datatagid}
    '''
    qid = '''select lsnum as lsnum, datatagid as datatagid from ids_datatag where datatagnameid=:datatagnameid and runnum=:runnum'''
    result = {}
    with connection.begin() as trans:
        idresult = connection.execute(qid,{'datatagnameid':datatagnameid,'runnum':runnum})
        for r in idresult:
            result[r['lsnum'] ] = r['datatagid']
    return result

def transfertimeinfo(connection,destconnection,runnum):
    '''
    query timeinformation of a given run
    '''
    q = """select lhcfill,runnumber,lumisection,to_char(starttime,'%s') as starttime from CMS_RUNTIME_LOGGER.LUMI_SECTIONS where runnumber=:runnum"""%(dbtimefm)
    i = """insert into TIMEINDEX(FILLNUM,RUNNUM,LSNUM,TIMESTAMPSEC,TIMESTAMPMSEC,TIMESTAMPSTR,WEEKOFYEAR,DAYOFYEAR,DAYOFWEEK,YEAR,MONTH) values(:fillnum, :runnum, :lsnum, :timestampsec, :timestampmsec, :timestampstr, :weekofyear, :dayofyear, :dayofweek, :year, :month)"""
    with connection.begin() as trans:
        result = connection.execute(q,{'runnum':runnum})        
        allrows = []
        for r in result:
            irow = {'fillnum':0,'runnum':runnum,'lsnum':0,'timestampsec':0,'timestampmsec':0,'timestampstr':'','weekofyear':0,'dayofyear':0,'dayofweek':0,'year':0,'month':0}
            irow['fillnum'] = r['lhcfill']
            irow['lsnum'] = r['lumisection']
            starttimestr = r['starttime']
            irow['timestampstr'] = starttimestr
            #stoptimestr = r['stoptime']
            starttime = datetime.strptime(starttimestr,pydatetimefm)
            irow['timestasec'] = time.mktime(starttime.timetuple())
            irow['timestamsec'] = starttime.microsecond/1e3
            irow['weekofyear'] = starttime.date().isocalendar()[1]
            irow['dayofyear'] = starttime.timetuple().tm_yday
            irow['dayofweek'] = starttime.date().isoweekday()
            irow['year'] = starttime.date().year
            irow['month'] = starttime.date().month
            allrows.append(irow)
    with destconnection.begin() as trans:
        r = destconnection.execute(i,allrows)

def transfer_ids_datatag(connection,destconnection,runnum,lumidataid):
    '''
    '''
    norb = 262144
    cmson = True
    qrunsummary = '''select r.FILLNUM as fillnum,r.EGEV as targetegev, r.AMODETAG as amodetag, s.LUMILSNUM as lsnum, s.CMSLSNUM as cmslsnum, s.BEAMSTATUS as beamstatus, to_char(t.STARTTIME,'%s') as starttime from CMS_LUMI_PROD.CMSRUNSUMMARY r, CMS_LUMI_PROD.LUMISUMMARYV2 s,  CMS_RUNTIME_LOGGER.LUMI_SECTIONS t where r.runnum=s.runnum and t.runnumber=s.runnum and s.lumilsnum=t.lumisection and r.runnum=:runnum and s.data_id=:lumidataid'''%(dbtimefm)
    i = """insert into IDS_DATATAG(DATATAGNAMEID,DATATAGID,FILLNUM,RUNNUM,LSNUM,TIMESTAMPSEC,CMSON,NORB,TARGETEGEV,BEAMSTATUS,AMODETAG) values(:datatagnameid, :datatagid, :fillnum, :runnum, :lsnum, :timestampsec, :cmson, :norb, :targetegev, :beamstatus, :amodetag)"""
    
    datatagnameid = 0    
    allrows = []
    with connection.begin() as trans:
        result = connection.execute(qrunsummary,{'runnum':runnum,'lumidataid':lumidataid})
        for r in result:
            lsnum = r['lsnum']
            cmslsnum = r['cmslsnum']
            if not cmslsnum: cmson=False
            starttimestr = r['starttime']
            starttime = datetime.strptime(starttimestr,pydatetimefm)
            k = next(api.generate_key(lsnum))
            irow = {'datatagnameid':datatagnameid, 'datatagid':k, 'fillnum':0,'runnum':runnum,'lsnum':0,'timestampsec':0,'cmson':cmson,'norb':norb,'targetegev':0,'beamstatus':'','amodetag':''}
            irow['datatagid'] = k
            irow['fillnum'] = r['fillnum']
            irow['lsnum'] = lsnum
            irow['timestampsec'] = time.mktime(starttime.timetuple())
            irow['targetegev'] = r['targetegev']
            irow['beamstatus'] = r['beamstatus']
            irow['amodetag'] = r['amodetag']            
            allrows.append(irow)
            #print datatagnameid,runnum,irow['lsnum']
    with destconnection.begin() as trans:
        r = destconnection.execute(i,allrows)

def transfer_runinfo(connection,destconnection,runnum,trgdataid,destdatatagid):
    '''
    prerequisite : ids_datatag has already entries for this run
    '''    
    qconfigid = '''select cast(STRING_VALUE as INT) as hltconfigid from CMS_RUNINFO.RUNSESSION_PARAMETER where NAME='CMS.LVL0:HLT_KEY' and RUNNUMBER=:runnum'''
    qruninfo = '''select fillnum,hltkey,l1key from CMS_LUMI_PROD.CMSRUNSUMMARY where runnum=:runnum'''
    qnbx = '''select INJECTIONSCHEME as fillscheme, NCOLLIDINGBUNCHES as ncollidingbx from CMS_RUNTIME_LOGGER.RUNTIME_SUMMARY where LHCFILL=:fillnum'''
    qmask = '''select ALGOMASK_H as algomask_high,ALGOMASK_L as algomask_low,TECHMASK as techmask from CMS_LUMI_PROD.trgdata where DATA_ID=:trgdataid'''
    i = '''insert into RUNINFO(DATATAGID,RUNNUM,HLTKEY,HLTCONFIGID,GT_RS_KEY,TRGMASK1,TRGMASK2,TRGMASK3,TRGMASK4,TRGMASK5,TRGMASK6,FILLSCHEME,BXPATTERN,NCOLLIDINGBX,NBPERLS) values(:datatagid, :runnum, :hltkey, :hltconfigid, :l1key, :trgmask1, :trgmask2, :trgmask3, :trgmask4, :trgmask5, :trgmask6, :fillscheme, :bxpattern, :ncollidingbx, :nbperls)'''
    
    allrows = []
    nbperls = 64
    hltkey = ''
    l1key = ''
    fillscheme = ''
    hltconfigid = 0
    fillnum = 0
    ncollidingbx = 0
    bxpattern = None
    trgmask1 = trgmask2 = trgmask3 = trgmask4 = trgmask5 = trgmask6 = 0
    
    with connection.begin() as trans:
        hltconfigresult = connection.execute(qconfigid,{'runnum':runnum})
        
        for r in hltconfigresult:
            hltconfigid = r['hltconfigid']

        runinforesult = connection.execute(qruninfo,{'runnum':runnum})
        for r in runinforesult:
            fillnum = r['fillnum']
            hltkey = r['hltkey']
            l1key = r['l1key']
            
        runtimeloggerresult = connection.execute(qnbx,{'fillnum':fillnum})
        for r in runtimeloggerresult:
            fillscheme = r['fillscheme']
            ncollidingbx = r['ncollidingbx']
            
        maskresult = connection.execute(qmask,{'trgdataid':trgdataid})
        for r in maskresult:
            algomask_high = r['algomask_high']
            algomask_low = r['algomask_low']
            techmask = r['techmask']
            (trgmask1,trgmask2) = unpack64to32(algomask_high)
            (trgmask3,trgmask4) = unpack64to32(algomask_low)
            (trgomask5,trgmask6) = unpack64to32(techmask)
            
        #for r in result:
        #    irow = {'datatagid':destdatatagid, 'runnum':runnum,'hltkey':'','l1key':'','trgmask':trgmask,'fillscheme':'','nbperls':nbperls}
        #    irow['hltkey'] = r['hltkey']
        #    irow['l1key'] = r['l1key']
        #    irow['fillscheme'] = r['fillscheme']

        irow = {'datatagid':destdatatagid, 'runnum':runnum, 'hltkey':hltkey, 'hltconfigid':hltconfigid, 'l1key':l1key, 'trgmask1':trgmask1, 'trgmask2':trgmask2, 'trgmask2':trgmask2, 'trgmask3':trgmask3, 'trgmask4':trgmask4, 'trgmask5':trgmask5, 'trgmask6':trgmask6, 'fillscheme':fillscheme, 'ncollidingbx': ncollidingbx, 'bxpattern':bxpattern, 'nbperls': nbperls}
        print irow
        allrows.append(irow)
    with destconnection.begin() as trans:
        r = destconnection.execute(i,allrows)

def transfer_beamintensity(connection,destconnection,shardid,runnum,lumidataid,destdatatagidmap):
    '''
    prerequisite : ids_datatag has already entries for this run
    '''
    
    qbeam = '''select l.LUMILSNUM as lsnum,l.BEAMENERGY as beamenergy,l.CMSBXINDEXBLOB as cmsbxindexblob, l.BEAMINTENSITYBLOB_1 as beamintensityblob_1,l.BEAMINTENSITYBLOB_2 as beamintensityblob_2,r.BEAM1_INTENSITY as beam1intensity, r.BEAM2_INTENSITY as beam2intensity from CMS_LUMI_PROD.lumisummaryv2 l, CMS_RUNTIME_LOGGER.LUMI_SECTIONS r where l.LUMILSNUM=r.LUMISECTION and l.RUNNUM=r.RUNNUMBER and l.DATA_ID=:lumidataid'''
    destTable = Table('BEAM_%d'%shardid, MetaData(), Column('DATATAGID',types.BigInteger),Column('EGEV',types.Float),Column('INTENSITY1',types.Float),Column('INTENSITY2',types.Float),Column('BXIDXBLOB',types.BLOB),Column('BXINTENSITY1BLOB',types.BLOB),Column('BXINTENSITY2BLOB',types.BLOB))    
    allbeamrows = []
    #print destdatatagidmap
    with connection.begin() as trans:
        result = connection.execute(qbeam,{'lumidataid':lumidataid})
        for row in result:
            lsnum = row['lsnum']
            beamenergy = row['beamenergy']
            bxidxblob = row['cmsbxindexblob']
            beamintensity1blob = row['beamintensityblob_1']
            beamintensity2blob = row['beamintensityblob_2']
            if not bxidxblob or not beamintensity1blob or not beamintensity2blob:
                continue
            beam1intensity = row['beam1intensity']
            beam2intensity = row['beam2intensity']
            
            ibeamrow = {'datatagid':destdatatagidmap[lsnum],'egev':beamenergy, 'intensity1':beam1intensity, 'intensity2':beam2intensity, 'bxidxblob':bxidxblob, 'bxintensity1blob':beamintensity1blob, 'bxintensity2blob':beamintensity2blob } 
            allbeamrows.append(ibeamrow)
    with destconnection.begin() as trans:
        for r in allbeamrows:
            destconnection.execute( destTable.insert(),DATATAGID=r['datatagid'],EGEV=r['egev'],INTENSITY1=r['intensity1'],INTENSITY2=r['intensity2'],BXIDXBLOB=r['bxidxblob'],BXINTENSITY1BLOB=r['bxintensity1blob'], BXINTENSITY2BLOB=r['bxintensity2blob'] )
            
def transfer_trgdata(connection,destconnection,shardid,runnum,trgdataid,destdatatagidmap):
    '''
    prerequisite : ids_datatag has already entries for this run
    '''
    bitnamemap = pd.DataFrame.from_csv('trgbits.csv',index_col='bitnameid')
    qalgobits = '''select ALGO_INDEX as bitid, ALIAS as bitname from CMS_GT.GT_RUN_ALGO_VIEW where RUNNUMBER=:runnum'''
    qprescidx = 'select lumi_section as lsnum, prescale_index as prescidx from CMS_GT_MON.LUMI_SECTIONS where run_number=:runnum and prescale_index!=0'
    
    qpresc = '''select cmslsnum as lsnum, prescaleblob as prescaleblob, trgcountblob as trgcountblob from CMS_LUMI_PROD.lstrg where data_id=:trgdataid'''
    i = '''insert into TRG_%d(DATATAGID,BITID,BITNAMEID,PRESCIDX,PRESCVAL,COUNTS) values(:datatagid, :bitid, :bitnameid, :prescidx, :prescval, :counts)'''%shardid

    allrows = []
    algobitalias = 128*['False']
    bitaliasmap = {}
    prescidxmap = {}
    with connection.begin() as trans:
        algoresult = connection.execute(qalgobits,{'runnum':runnum})
        for algo in algoresult:
            bitid = algo['bitid']
            algobitalias[bitid] = algo['bitname']
            
        prescidxresult = connection.execute(qprescidx,{'runnum':runnum})
        for prescidxr in prescidxresult:
            lsnum = prescidxr['lsnum']
            prescidx = prescidxr['prescidx']
            prescidxmap[lsnum] = prescidx
    #print prescidxmap
    for bitnameid, bitparams in bitnamemap.iterrows():
        bitname = bitparams['bitname']
        bitid = bitparams['bitid']
        bitaliasmap[bitname] = [bitnameid,bitid]

    with connection.begin() as trans:
        result = connection.execute(qpresc,{'trgdataid':trgdataid})        
        for row in result:
            lsnum = row['lsnum']
            if runnum<150008:
                try:
                    prescblob = unpackblobstr(row['prescaleblob'],'l')
                    trgcountblob = unpackblobstr(row['trgcountblob'],'l')
                    if not prescblob or not trgcountblob:
                        continue
                except ValueError:
                    prescblob = unpackblobstr(row['prescaleblob'],'I')
                    trgcountblob = unpackblobstr(row['trgcountblob'],'I')
                    if not prescblob or not trgcountblob:
                        continue
            else:
                prescblob = unpackblobstr(row['prescaleblob'],'I')
                trgcountblob = unpackblobstr(row['trgcountblob'],'I')
                if not prescblob or not trgcountblob:
                    continue
            prescalevalues = pd.Series(prescblob)
            trgcountvalues = pd.Series(trgcountblob)

            for idx, prescval in prescalevalues.iteritems(): #192 values 0,127 algo,128-191 tech
                bitid = 0
                bitname = ''
                if idx>127:
                    bitname = str(idx-128)
                else:
                    bitname = algobitalias[idx]                    
                    if bitname =='False':
                        continue
                    
                if bitaliasmap.has_key(bitname):
                    bitnameid = bitaliasmap[bitname][0]
                    bitid = bitaliasmap[bitname][1]
                else:
                    print 'unknown bitname %s'%bitname
                    continue
                
                counts = 0
                prescidx = 0
                try:
                    counts = trgcountvalues[idx]
                except IndexError:
                    pass
                try:
                    prescidx = prescidxmap[lsnum]
                except KeyError:
                    pass
                allrows.append({'datatagid':destdatatagidmap[lsnum], 'bitid':bitid, 'bitnameid':bitnameid, 'prescidx':prescidx ,'prescval':prescval, 'counts':counts})
                
    with destconnection.begin() as trans:
        r = destconnection.execute(i,allrows)

def transfer_hltdata(connection,destconnection,shardid,runnum,hltdataid,destdatatagidmap):
    '''
    prerequisite : ids_datatag has already entries for this run
    '''
    p = re.compile('^HLT_+',re.IGNORECASE)
    pathnamedf = pd.DataFrame.from_csv('hltpaths.csv',index_col=False)
    pathnamemap = {}
    for i,row in pathnamedf.iterrows():
        n =row['hltpathname']
        if p.match(n) is None:
            continue
        d = row['hltpathid']
        pathnamemap.setdefault(n,[]).append( int(d) )
    #print pathnamemap
    #print pathnamemap.keys()

    qprescidx = '''select lumi_section as lsnum, prescale_index as prescidx from CMS_GT_MON.LUMI_SECTIONS where run_number=:runnum and prescale_index!=0'''

    qpathname = '''select pathnameclob from CMS_LUMI_PROD.HLTDATA where data_id=:hltdataid'''
    
    qhlt = '''select cmslsnum as lsnum, prescaleblob as prescaleblob, hltcountblob as hltcountblob, hltacceptblob as hltacceptblob from CMS_LUMI_PROD.LSHLT where data_id=:hltdataid'''    

    qpathid = '''select lsnumber as lsnum, pathid as hltpathid from cms_runinfo.hlt_supervisor_triggerpaths where runnumber=:runnum'''
    
    i = '''insert into HLT_%d(DATATAGID,HLTPATHID,PRESCIDX,PRESCVAL,L1PASS,HLTACCEPT) values(:datatagid, :hltpathid, :prescidx, :prescval, :l1pass, :hltaccept)'''%shardid
    
    allrows = []
    
    prescidxmap = {}
    
    lspathids = {}
    
    with connection.begin() as trans:
        prescidxresult = connection.execute(qprescidx,{'runnum':runnum})
        for prescidxr in prescidxresult:
            lsnum = prescidxr['lsnum']
            prescidx = prescidxr['prescidx']
            prescidxmap[lsnum] = prescidx

    with connection.begin() as trans:
        lspathidresult = connection.execute(qpathid,{'runnum':runnum})
        for lspathr in lspathidresult:
            lsnum = lspathr['lsnum']
            hltpathid = lspathr['hltpathid']
            lspathids.setdefault(lsnum,[]).append(hltpathid)
    
    with connection.begin() as trans:
        pathnameresult = connection.execute(qpathname,{'hltdataid':hltdataid})        
        for row in pathnameresult:
            pathnameclob = row['pathnameclob']
            pathnames = pathnameclob.split(',')

        hltresult = connection.execute(qhlt,{'hltdataid':hltdataid})
        for row in hltresult:
            lsnum = row['lsnum']
            if runnum<150008:
                try:
                    prescblob = unpackblobstr(row['prescaleblob'],'l')
                    hltcountblob = unpackblobstr(row['hltcountblob'],'l')
                    hltacceptblob = unpackblobstr(row['hltacceptblob'],'l')
                    if not prescblob or not hltcountblob or not hltacceptblob:
                        continue
                except ValueError:
                    prescblob = unpackblobstr(row['prescaleblob'],'I')
                    hltcountblob = unpackblobstr(row['hltcountblob'],'I')
                    hltacceptblob = unpackblobstr(row['hltacceptblob'],'I')
                    if not prescblob or not hltcountblob or not hltacceptblob:
                        continue
            else:
                prescblob = unpackblobstr(row['prescaleblob'],'I')
                hltcountblob = unpackblobstr(row['hltcountblob'],'I')
                hltacceptblob = unpackblobstr(row['hltacceptblob'],'I')
                if not prescblob or not hltcountblob or not hltacceptblob:
                    continue
            prescalevalues = pd.Series(prescblob)
            hltcountvalues = pd.Series(hltcountblob)
            hltacceptvalues = pd.Series(hltacceptblob)
            
            for idx, prescval in prescalevalues.iteritems():
                prescidx = 0
                hltcounts = 0
                hltaccept = 0
                hltpathname = ''
                hltpathid = 0
                try:
                    hltpathname = pathnames[idx]
                except IndexError:
                    pass
                if p.match(hltpathname) is None: continue
                if hltpathname.find('Calibration')!=-1: continue
                try:
                    hltcounts = hltcountvalues[idx]
                except IndexError:
                    pass
                try:
                    hltaccept = hltacceptvalues[idx]
                except IndexError:
                    pass
                try:
                    prescidx = prescidxmap[lsnum]
                except KeyError:
                    pass
                pathidcandidates = pathnamemap[hltpathname]
                try:
                    pathidinsersection = list( set(pathidcandidates) & set(lspathids[lsnum]) )
                    hltpathid = pathidinsersection[0]
                except KeyError:
                    print 'no hltpath found for ls %d, skip'%(lsnum)
                    continue
                allrows.append({'datatagid':destdatatagidmap[lsnum], 'hltpathid':hltpathid, 'prescidx':prescidx, 'prescval':prescval, 'l1pass':hltcounts, 'hltaccept':hltaccept})

    with destconnection.begin() as trans:
        r = destconnection.execute(i,allrows)



def transfer_lumidata(connection,destconnection,shardid,runnum,lumidataid,destdatatagidmap):
    '''
    prerequisite : ids_datatag has already entries for this run
    '''
    qlumioc = '''select LUMILSNUM as lsnum, INSTLUMI as rawlumi, BXLUMIVALUE_OCC1 as bxrawlumiblob from CMS_LUMI_PROD.LUMISUMMARYV2 where DATA_ID=:lumidataid'''
    destTable = Table('HFOC_%d'%shardid, MetaData(), Column('DATATAGID',types.BigInteger), Column('RAWLUMI',types.Float), Column('BXRAWLUMIBLOB',types.BLOB ) )
    allrows = []
    with connection.begin() as trans:
        lumiresult = connection.execute(qlumioc,{'lumidataid':lumidataid})
        for row in lumiresult:
            lsnum = row['lsnum']
            rawlumi = row['rawlumi']
            bxrawlumiblob = row['bxrawlumiblob']            
            bxrows = []
            allrows.append( {'datatagid':destdatatagidmap[lsnum] , 'rawlumi':rawlumi, 'bxrawlumiblob':bxrawlumiblob})
            
    with destconnection.begin() as trans:
        for r in allrows:
            destconnection.execute( destTable.insert(),DATATAGID=r['datatagid'],RAWLUMI=r['rawlumi'],BXRAWLUMIBLOB=r['bxrawlumiblob'] )
            
def transfer_deadtime(connection,destconnection,shardid,runnum,trgdataid,destdatatagidmap):
    '''
    prerequisite : ids_datatag has already entries for this run
    '''
    q = '''select CMSLSNUM as lsnum,DEADFRAC as deadfrac from CMS_LUMI_PROD.LSTRG where DATA_ID=:trgdataid'''

    i = '''insert into DEADTIME_%d(DATATAGID,DEADTIMEFRAC) values(:datatagid,:deadtimefrac)'''%shardid
    
    with connection.begin() as trans:
        allrows = []
        result = connection.execute(q,{'trgdataid':trgdataid})
        deadtimefrac = 1.
        for row in result:
            lsnum = row['lsnum']
            deadfrac = row['deadfrac']
            allrows.append({'datatagid':destdatatagidmap[lsnum], 'deadtimefrac':deadfrac})
    with destconnection.begin() as trans:
        r = destconnection.execute(i,allrows)
    
if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    parser = SafeConfigParser()
    parser.read('readdb2.ini')
    
    runinfoconnectstr = 'oracle://cms_runinfo_r@cms_orcon_adg'
    runinfopasswd = parser.get(runinfoconnectstr,'pwd')
    idx = runinfoconnectstr.find('@')
    pcode = base64.b64decode(runinfopasswd).decode('UTF-8')
    runinfoconnecturl = runinfoconnectstr[:idx]+':'+pcode+runinfoconnectstr[idx:]
    runinfoengine = create_engine(runinfoconnecturl)
    runinfoconnection = runinfoengine.connect().execution_options(stream_results=True)


    trgconnectstr = 'oracle://cms_trg_r@cms_orcon_adg'
    trgpasswd = parser.get(trgconnectstr,'pwd')
    idx = trgconnectstr.find('@')
    trgcode = base64.b64decode(trgpasswd).decode('UTF-8')
    trgconnecturl = trgconnectstr[:idx]+':'+trgcode+trgconnectstr[idx:]
    trgengine = create_engine(trgconnecturl)
    trgconnection = trgengine.connect().execution_options(stream_results=True)
    
    desturl = 'sqlite:///test.db'
    destengine = create_engine(desturl)
    destconnection = destengine.connect()    
    
    ids = [ [165523,279,278,269],[193091,1649,1477,1391] ]    
    for [run,lumidataid,trgdataid,hltdataid] in ids:
        shardid = getshardid(destconnection,run)
        if not shardid:
            print 'cannot find shard for run %d'%run
            continue
        print 'shardid: %d'%shardid
        print 'processing %d,%d,%d,%d'%(run,lumidataid,trgdataid,hltdataid)
        transfertimeinfo(runinfoconnection,destconnection,run)
        transfer_ids_datatag(runinfoconnection,destconnection,run,lumidataid)
        destdatatagid = datatagid_of_run(destconnection,run,datatagnameid=0)
        destdatatagid_map = datatagid_of_ls(destconnection,run,datatagnameid=0)
        transfer_runinfo(runinfoconnection,destconnection,run,trgdataid,destdatatagid)
        transfer_beamintensity(runinfoconnection,destconnection,shardid,run,lumidataid,destdatatagid_map)
        transfer_trgdata(trgconnection,destconnection,shardid,run,trgdataid,destdatatagid_map)
        transfer_hltdata(trgconnection,destconnection,shardid,run,hltdataid,destdatatagid_map)
        transfer_lumidata(runinfoconnection,destconnection,shardid,run,lumidataid,destdatatagid_map)
        transfer_deadtime(runinfoconnection,destconnection,shardid,run,trgdataid,destdatatagid_map)

    
