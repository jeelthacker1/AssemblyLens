"""Train and export a CVAT-box detector. Requires photographed data and requirements-ml.txt.
Validation is image-level held-out; no trained artifact or accuracy is bundled.
"""
import argparse,hashlib,json,random,time
from pathlib import Path
import cv2,numpy as np
from backend.training import parse_cvat

def main():
    import torch,torchvision
    from torch.utils.data import DataLoader,Dataset
    p=argparse.ArgumentParser();p.add_argument('annotations');p.add_argument('images');p.add_argument('--epochs',type=int,default=10);p.add_argument('--batch-size',type=int,default=2);p.add_argument('--device',default='cpu');p.add_argument('--output',default='data/detector');p.add_argument('--pretrained',action='store_true');p.add_argument('--mlflow');args=p.parse_args()
    torch.manual_seed(42);random.seed(42);np.random.seed(42)
    annotation_bytes=Path(args.annotations).read_bytes();rows=parse_cvat(annotation_bytes)
    if len(rows)<10:raise ValueError('At least 10 annotated images required; collect representative real examples')
    labels=sorted({a['label'] for row in rows for a in row['annotations'] if 'bbox' in a});random.shuffle(rows);split=int(len(rows)*.8)
    root=Path(args.images).resolve();device=torch.device(args.device)
    class Images(Dataset):
        def __init__(self,rows):self.rows=rows
        def __len__(self):return len(self.rows)
        def __getitem__(self,index):
            row=self.rows[index];path=(root/row['name']).resolve()
            if not path.is_relative_to(root):raise ValueError('Invalid dataset path')
            image=cv2.imread(str(path))
            if image is None:raise ValueError('Missing image '+row['name'])
            tensor=torch.from_numpy(cv2.cvtColor(cv2.resize(image,(640,640)),cv2.COLOR_BGR2RGB).transpose(2,0,1).copy()).float()/255
            boxes=[];classes=[]
            for a in row['annotations']:
                if 'bbox' not in a:continue
                x,y,w,h=a['bbox'];boxes.append([x*640,y*640,(x+w)*640,(y+h)*640]);classes.append(labels.index(a['label'])+1)
            return tensor,{'boxes':torch.tensor(boxes,dtype=torch.float32).reshape(-1,4),'labels':torch.tensor(classes,dtype=torch.int64)}
    train=Images(rows[:split]);validation=Images(rows[split:])
    model=torchvision.models.detection.fasterrcnn_mobilenet_v3_large_320_fpn(weights='DEFAULT' if args.pretrained else None,weights_backbone=None)
    model.roi_heads.box_predictor=torchvision.models.detection.faster_rcnn.FastRCNNPredictor(model.roi_heads.box_predictor.cls_score.in_features,len(labels)+1)
    model.to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.0001)
    for epoch in range(args.epochs):
        model.train();losses=[]
        for images,targets in DataLoader(train,batch_size=args.batch_size,shuffle=True,collate_fn=lambda batch:tuple(zip(*batch))):
            loss=sum(model([i.to(device) for i in images],[{k:v.to(device) for k,v in t.items()} for t in targets]).values())
            optimizer.zero_grad();loss.backward();optimizer.step();losses.append(float(loss.detach()))
        print(json.dumps({'epoch':epoch+1,'loss':float(np.mean(losses))}),flush=True)
    model.eval();tp=fp=fn=0;latencies=[]
    with torch.no_grad():
        for image,target in validation:
            if device.type=='cuda':torch.cuda.synchronize()
            start=time.perf_counter();prediction=model([image.to(device)])[0]
            if device.type=='cuda':torch.cuda.synchronize()
            latencies.append((time.perf_counter()-start)*1000)
            selected=prediction['scores']>=.5;boxes=prediction['boxes'][selected].cpu();classes=prediction['labels'][selected].cpu();used=set()
            overlaps=torchvision.ops.box_iou(boxes,target['boxes'])
            for index,cls in enumerate(classes):
                candidates=[(float(overlaps[index,j]),j) for j,t in enumerate(target['labels']) if t==cls and j not in used]
                score,j=max(candidates,default=(0,-1))
                if score>=.5:tp+=1;used.add(j)
                else:fp+=1
            fn+=len(target['boxes'])-len(used)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);model.cpu();torch.save(model.state_dict(),out/'detector.pt')
    class Export(torch.nn.Module):
        def __init__(self,model):super().__init__();self.model=model
        def forward(self,x):
            result=self.model([x[0]])[0]
            return torch.cat([result['boxes'],result['scores'][:,None],(result['labels']-1).float()[:,None]],dim=1)[None]
    wrapper=Export(model).eval()
    torch.onnx.export(wrapper,torch.zeros(1,3,640,640),str(out/'detector.onnx'),opset_version=17,input_names=['images'],output_names=['detections'],dynamic_axes={'detections':{1:'num_detections'}},dynamo=False)
    report={'labels':labels,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'iou_threshold':.5,'score_threshold':.5,'validation_images':[r['name'] for r in rows[split:]],'train_images':[r['name'] for r in rows[:split]],'dataset_sha256':hashlib.sha256(annotation_bytes).hexdigest(),'p95_inference_ms':float(np.percentile(latencies,95)),'epochs':args.epochs,'seed':42,'assembly_false_acceptance_rate':None,'assembly_false_rejection_rate':None,'note':'Detection metrics do not establish assembly-level quality. Run tools.evaluate with independently reviewed assemblies.'}
    (out/'report.json').write_text(json.dumps(report,indent=2));(out/'labels.json').write_text(json.dumps(labels))
    if args.mlflow:
        import mlflow
        mlflow.set_tracking_uri(args.mlflow)
        with mlflow.start_run():
            mlflow.log_params({'epochs':args.epochs,'dataset_sha256':report['dataset_sha256']});mlflow.log_metrics({k:v for k,v in report.items() if k in ('precision','recall','p95_inference_ms') and v is not None});mlflow.log_artifacts(str(out))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
