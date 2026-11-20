"""Confidence-distribution monitoring. A shift is a review signal, not proof of bad quality."""
from collections import deque
import numpy as np

def distribution(scores):
    values=np.asarray(scores,dtype=float)
    if len(values)==0 or not np.isfinite(values).all() or (values<0).any() or (values>1).any():
        raise ValueError('finite confidence samples in [0,1] required')
    counts,_=np.histogram(values,bins=np.linspace(0,1,11))
    return (counts/counts.sum()).tolist()

def population_stability(baseline,current):
    a=np.asarray(baseline,dtype=float);b=np.asarray(current,dtype=float)
    if a.shape!=(10,) or b.shape!=(10,) or not np.isfinite(a).all() or not np.isfinite(b).all() or min(a.min(),b.min())<0 or abs(a.sum()-1)>.01 or abs(b.sum()-1)>.01:
        raise ValueError('two normalized ten-bin distributions required')
    a=np.maximum(a,1e-5);b=np.maximum(b,1e-5)
    return float(np.sum((b-a)*np.log(b/a)))

class DriftMonitor:
    def __init__(self,baseline,window=100,threshold=.25):
        population_stability(baseline,baseline)
        self.baseline=baseline;self.values=deque(maxlen=window);self.threshold=threshold
    def update(self,score):
        self.values.append(float(score))
        if len(self.values)<self.values.maxlen:return {'model_drift':False,'drift_score':None,'drift_samples':len(self.values)}
        value=population_stability(self.baseline,distribution(self.values))
        return {'model_drift':value>self.threshold,'drift_score':value,'drift_samples':len(self.values)}
