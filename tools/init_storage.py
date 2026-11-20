"""Local Compose bucket initialization. Production buckets are provisioned separately."""
import os,time
import boto3
from botocore.exceptions import ClientError

client=boto3.client('s3',endpoint_url=os.environ['S3_ENDPOINT'])
bucket=os.environ['S3_BUCKET']
for attempt in range(30):
    try:
        try: client.head_bucket(Bucket=bucket)
        except ClientError as e:
            if e.response['Error']['Code'] in ('404','NoSuchBucket'): client.create_bucket(Bucket=bucket)
            else: raise
        client.put_bucket_lifecycle_configuration(Bucket=bucket,LifecycleConfiguration={'Rules':[{'ID':'evidence-90-days','Status':'Enabled','Filter':{'Prefix':''},'Expiration':{'Days':90}}]})
        print('Evidence bucket ready; 90-day object lifecycle configured.');break
    except Exception as e:
        if attempt==29: raise
        print(f'Waiting for object storage ({type(e).__name__})',flush=True);time.sleep(2)
