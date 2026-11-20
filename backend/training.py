"""CVAT import and honest metrics: undefined denominators are null, never perfect scores."""
from defusedxml import ElementTree

def parse_cvat(data):
    root=ElementTree.fromstring(data)
    if root.tag!='annotations': raise ValueError('CVAT annotations root required')
    images=[]
    for image in root.findall('image'):
        width=int(image.attrib['width']); height=int(image.attrib['height'])
        if width<=0 or height<=0: raise ValueError('invalid image size')
        annotations=[]
        for shape in image:
            if shape.tag=='box':
                x1,y1,x2,y2=[float(shape.attrib[k]) for k in ('xtl','ytl','xbr','ybr')]
                if not 0<=x1<x2<=width or not 0<=y1<y2<=height: raise ValueError('box outside image')
                annotations.append({'label':shape.attrib['label'],'bbox':[x1/width,y1/height,(x2-x1)/width,(y2-y1)/height]})
            elif shape.tag=='polygon': annotations.append({'label':shape.attrib['label'],'polygon':[[float(x)/width,float(y)/height] for x,y in (v.split(',') for v in shape.attrib['points'].split(';'))]})
        images.append({'name':image.attrib['name'],'width':width,'height':height,'annotations':annotations})
    if not images: raise ValueError('CVAT image task required (video interpolation tasks not supported)')
    return images

def quality_metrics(rows):
    """Rows: truth_good bool, predicted_good bool or null, latency_ms float.
    Review/uncertain is a separate outcome. FAR/FRR use all known bad/good items.
    """
    import numpy as np
    tp=sum(r['truth_good'] and r['predicted_good'] is True for r in rows)
    fp=sum(not r['truth_good'] and r['predicted_good'] is True for r in rows)
    tn=sum(not r['truth_good'] and r['predicted_good'] is False for r in rows)
    fn=sum(r['truth_good'] and r['predicted_good'] is False for r in rows)
    good=sum(r['truth_good'] for r in rows); bad=len(rows)-good
    ratio=lambda a,b:a/b if b else None
    lat=[r['latency_ms'] for r in rows]
    return {'n':len(rows),'precision':ratio(tp,tp+fp),'recall':ratio(tp,good),'false_acceptance_rate':ratio(fp,bad),'false_rejection_rate':ratio(fn,good),'uncertain_rate':ratio(sum(r['predicted_good'] is None for r in rows),len(rows)),'latency_p50_ms':float(np.percentile(lat,50)) if lat else None,'latency_p95_ms':float(np.percentile(lat,95)) if lat else None,'confusion':{'tp':tp,'fp':fp,'tn':tn,'fn':fn}}
