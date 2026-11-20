"""Train a real PyTorch crop classifier from CVAT boxes. Not an object detector.
Use this for component appearance research; deploy a separately validated detection export.
"""
import argparse
import hashlib
import json
from pathlib import Path
from backend.training import parse_cvat

def main():
    import torch
    from torch import nn
    import cv2
    import numpy as np
    p=argparse.ArgumentParser(); p.add_argument('annotations'); p.add_argument('images'); p.add_argument('--epochs',type=int,default=10); p.add_argument('--output',default='data/training'); p.add_argument('--mlflow',default=None); args=p.parse_args()
    torch.manual_seed(42); np.random.seed(42)
    annotations=Path(args.annotations).read_bytes(); rows=parse_cvat(annotations)
    labels=sorted({a['label'] for r in rows for a in r['annotations'] if 'bbox' in a})
    if len(labels)<2 or len(rows)<4: raise ValueError('Need >=2 classes and >=4 photographed images for an image-level train/validation split')
    split=max(1,int(len(rows)*.8)); datasets=[[],[]]; root=Path(args.images).resolve()
    for index,row in enumerate(rows):
        path=(root/row['name']).resolve()
        if not path.is_relative_to(root): raise ValueError('image path escapes dataset')
        image=cv2.imread(str(path))
        if image is None: raise ValueError(f'Missing image: {row["name"]}')
        h,w=image.shape[:2]
        for a in row['annotations']:
            if 'bbox' not in a: continue
            x,y,bw,bh=a['bbox']; crop=image[int(y*h):int((y+bh)*h),int(x*w):int((x+bw)*w)]
            tensor=torch.tensor(cv2.cvtColor(cv2.resize(crop,(64,64)),cv2.COLOR_BGR2RGB).transpose(2,0,1).copy(),dtype=torch.float32)/255
            datasets[index>=split].append((tensor,labels.index(a['label'])))
    if not all(datasets): raise ValueError('Both splits need annotated crops')
    model=nn.Sequential(nn.Conv2d(3,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),nn.Flatten(),nn.Linear(32,len(labels)))
    optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    train_x=torch.stack([r[0] for r in datasets[0]]); train_y=torch.tensor([r[1] for r in datasets[0]])
    for _ in range(args.epochs):
        model.train(); optimizer.zero_grad(); loss=nn.functional.cross_entropy(model(train_x),train_y); loss.backward(); optimizer.step()
    model.eval()
    with torch.no_grad():
        pred=model(torch.stack([r[0] for r in datasets[1]])).argmax(1); truth=torch.tensor([r[1] for r in datasets[1]])
        accuracy=float((pred==truth).float().mean())
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    torch.save(model.state_dict(),out/'classifier.pt')
    report={'task':'crop_classification_not_detection','labels':labels,'validation_accuracy':accuracy,'validation_crops':len(datasets[1]),'train_images':[r['name'] for r in rows[:split]],'validation_images':[r['name'] for r in rows[split:]],'annotation_sha256':hashlib.sha256(annotations).hexdigest(),'epochs':args.epochs,'seed':42}
    (out/'report.json').write_text(json.dumps(report,indent=2))
    if args.mlflow:
        import mlflow
        mlflow.set_tracking_uri(args.mlflow)
        with mlflow.start_run(): mlflow.log_params({'epochs':args.epochs,'dataset_sha':report['annotation_sha256']}); mlflow.log_metric('validation_accuracy',accuracy); mlflow.log_artifacts(str(out))
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
