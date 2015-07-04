_timeopt_pattern = '^\d\d/\d\d/\d\d \d\d:\d\d:\d\d$|^\d{6}$|^\d{4}$'
_fillnum_pattern = '^\d{4}$'
_runnum_pattern = '^\d{6}$'
_time_pattern = '^\d\d/\d\d/\d\d \d\d:\d\d:\d\d$'
_amodetagChoices = ['PROTPHYS','IONPHYS','PAPHYS']
_beamstatusChoices = ['FLAT TOP','SQUEEZE','ADJUST','STABLE BEAMS']
_lumitypeChoices = ['HFOC','HFET','PXL','BCM1F','PLT']
_applytoChoices = ['DAQ','LUMI','BKG']
_outstyle = ['tab','html','csv']
_dbtimefm = 'MM/DD/YY HH24:MI:SS.ff6'
_pydatetimefm  = '%m/%d/%y %H:%M:%S.%f'
_datetimefm = '%m/%d/%y %H:%M:%S'
_beamstatustoid = {'NO BEAM':0,'SETUP':1,'ABORT':2,'INJECTION PROBE BEAM':3,'INJECTION SETUP BEAM':4,'INJECTION PHYSICS BEAM':5,'PREPARE RAMP':6,'RAMP':7,'FLAT TOP':8,'SQUEEZE':9,'ADJUST':10,'STABLE BEAMS':11,'UNSTABLE BEAMS':12,'BEAM DUMP WARNING':13,'BEAM DUMP':14,'RAMP DOWN':15,'CYCLING':16,'RECOVERY':17,'INJECT & DUMP':18,'CIRCULATE & DUMP':19,'UNKNOWN':20}
_idtobeamstatus = dict( (v,k) for k,v in _beamstatustoid.items() )
_amodetagtoid = {'UNKNOWN':0,'PROTPHYS':1,'IONPHYS':2,'PAPHYS':3,'APPHYS':4,'TOTEMPHYS':5}
_idtoamodetag = dict( (v,k) for k,v in _amodetagtoid.items() )

