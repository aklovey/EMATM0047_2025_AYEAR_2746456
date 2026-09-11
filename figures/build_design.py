from pathlib import Path
import json
import xml.etree.ElementTree as ET

out=Path(__file__).resolve().parent
out.mkdir(parents=True,exist_ok=True)
mx=ET.Element('mxfile',host='app.diagrams.net',type='device',version='29.0.3')
diagram=ET.SubElement(mx,'diagram',id='two-cohort-design',name='Evaluation design')
model=ET.SubElement(diagram,'mxGraphModel',dx='1200',dy='610',grid='1',gridSize='10',guides='1',tooltips='1',connect='1',arrows='1',fold='1',page='1',pageScale='1',pageWidth='1200',pageHeight='610',math='0',shadow='0',background='#FFFFFF')
root=ET.SubElement(model,'root')
ET.SubElement(root,'mxCell',id='0')
ET.SubElement(root,'mxCell',id='1',parent='0')
base='rounded=1;arcSize=8;whiteSpace=wrap;html=0;fontFamily=Arial;fontSize=22;fontColor=#253746;align=center;verticalAlign=middle;spacing=8;strokeWidth=1.4;'
def box(id,text,x,y,w,h,fill='#F3F7FA',stroke='#8194A2',extra=''):
    cell=ET.SubElement(root,'mxCell',id=id,value=text,style=base+f'fillColor={fill};strokeColor={stroke};'+extra,vertex='1',parent='1')
    ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
def label(id,text,x,y,w,h,size=22,bold=False):
    box(id,text,x,y,w,h,'none','none',f'shape=text;rounded=0;spacing=0;fontSize={size};fontStyle={1 if bold else 0};')
def edge(id,source,target,points=None,extra=''):
    cell=ET.SubElement(root,'mxCell',id=id,style='edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;endFill=1;strokeColor=#5A7182;strokeWidth=1.8;'+extra,edge='1',parent='1',source=source,target=target)
    g=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
    if points:
        array=ET.SubElement(g,'Array',attrib={'as':'points'})
        for x,y in points: ET.SubElement(array,'mxPoint',x=str(x),y=str(y))

label('title','Two cohorts, one frozen comparison',20,10,1160,34,27,True)
box('shared-bank','Shared pool: 56 IDs | PNS version: 52 compressed traces + 4 parent fallbacks',80,58,1040,44,'#EEF2F7','#CBD5DE','fontSize=23;')
label('conditions','ZERO (no examples)  |  Three 2-shot conditions: FULL, HEURISTIC, PNS',20,112,1160,28,21)
label('control','Same example identities and order in the 2-shot conditions; same output cap per target in all four.',20,143,1160,26,20)

label('main-title','a  Previously evaluated cohort',20,180,600,30,24,True)
box('main-source','Previously evaluated\nCLADDER inventory',20,220,250,108)
box('main-cohort','300 targets\n271 full-CPT groups\n59 share prior CPTs',310,220,230,108,extra='fontSize=21;')
box('main-eval','4 conditions\n1,200 requests',580,220,245,108)
box('main-analysis','271-group bootstrap\nGroup sign-flip tests\n3 PNS comparisons',865,220,300,108,'#EDF2F8','#7089A4')
edge('main-select','main-source','main-cohort')
edge('main-requests','main-cohort','main-eval')
edge('main-stats','main-eval','main-analysis')

label('fresh-title','b  New numerical instances',20,357,600,30,24,True)
box('fresh-source','Official generator\nExisting graph families\nand story templates',20,398,250,112,extra='fontSize=21;')
box('fresh-cohort','257 proposals\n11 excluded\n246 retained',310,398,230,112)
box('fresh-eval','4 conditions\n984 requests',580,398,245,112)
box('fresh-analysis','246-instance bootstrap\nExact McNemar tests\n3 PNS comparisons',865,398,300,112,'#EDF2F8','#7089A4','fontSize=21;')
edge('fresh-filter','fresh-source','fresh-cohort')
edge('fresh-requests','fresh-cohort','fresh-eval')
edge('fresh-stats','fresh-eval','fresh-analysis')
label('filters','Fixed validity and novelty filters',220,516,425,26,20)
box('holm','Joint Holm adjustment of six p-values\nThe target outcomes remain in separate cohorts',530,559,635,66,'#F1EDF3','#8F7C95','fontSize=21;')
edge('main-pvalues','main-analysis','holm',[(1188,274),(1188,592)],'exitX=1;exitY=0.5;entryX=1;entryY=0.5;')
edge('fresh-pvalues','fresh-analysis','holm',None,'exitX=0.5;exitY=1;entryX=0.8;entryY=0;')

tree=ET.ElementTree(mx)
ET.indent(tree,space='  ')
tree.write(out/'figure4_1_evaluation_design.drawio',encoding='utf-8',xml_declaration=True)
caption='''Figure 4.1: Evaluation cohorts and analysis units. Both cohorts used the same 56-identity demonstration policy and four conditions. The 300 previously evaluated targets formed 271 groups defined by their graph and complete conditional probability tables; 59 targets shared full CPTs with earlier material. The fresh cohort retained 246 distinct numerical instances from 257 proposals after fixed validity and novelty checks, using existing graph families and story templates. Bootstrap and paired-test procedures remained cohort-specific. Only the six prespecified p-values entered the joint Holm correction; target outcomes were not pooled. The shared output cap applies within each target, not as one numeric cap across targets.'''
(out/'figure4_1_caption.md').write_text(caption+'\n',encoding='utf-8')
contract={'claim':'The same frozen policy was evaluated in two distinct cohorts with different sampling and inference units.','archetype':'native method diagram','role':'clarify evaluation design and separate cohort inference','source_facts':{'demo_identities':56,'accepted':52,'fallback':4,'main_targets':300,'main_cpt_groups':271,'main_prior_cpt_overlap_targets':59,'main_requests':1200,'fresh_proposals':257,'fresh_excluded':11,'fresh_retained':246,'fresh_requests':984,'joint_pvalues':6},'native_vertices':sum(c.get('vertex')=='1' for c in root),'native_connectors':sum(c.get('edge')=='1' for c in root),'source_file':'figure4_1_evaluation_design.drawio','caption_file':'figure4_1_caption.md'}
(out/'figure4_1_provenance.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
print(json.dumps(contract))

