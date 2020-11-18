import json
import logging
import boto3
import base64
import time
import math
import random
from boto3.dynamodb.conditions import Key, Attr

from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def get_table(table_name):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    return table

def create_index(key):
    s3 = boto3.resource('s3')
    copy_source = {
        'Bucket': 'smart-door-visitor',
        'Key': key
    }
    s3.meta.client.copy(copy_source, 'cc-hw2-b1', key)
    client = boto3.client('rekognition')
    collection_id = "visitors_collection"
    response = client.index_faces(CollectionId=collection_id,
                                Image={'S3Object':{'Bucket':'cc-hw2-b1','Name':key}},
                                ExternalImageId=key,
                                MaxFaces=1,
                                QualityFilter="AUTO",
                                DetectionAttributes=['ALL'])
    
    logger.debug('Faces indexed:')		
    face_id = ''
    for faceRecord in response['FaceRecords']:
         face_id = faceRecord['Face']['FaceId']
         logger.debug('  Face ID: %s' % faceRecord['Face']['FaceId'])
         print('  Location: {}'.format(faceRecord['Face']['BoundingBox']))
    return face_id

def generateOTP(): 
    digits = "0123456789"
    OTP = "" 
    for i in range(6) : 
        OTP += digits[math.floor(random.random() * 10)] 
    return OTP     

def send_otp(face_id, phone_number):
    table = get_table('virtual_door_passcodes')
    otp = generateOTP()
    exists = True
    while exists == True:
        response = table.query(
            KeyConditionExpression=Key('passcode').eq(otp)
        )
        if response['Items']:
            logger.debug("passcode found in the db")
            otp = generateOTP()
        else:
            exists = False
            
    table.put_item(Item = {'passcode' : otp, 'face_id' : face_id, 'passcode_time' : int(time.time() + 300)})        
    try:
        client = boto3.client('sns')
        phone_number = "+1"+phone_number
        msg = "Your door entry code is: " + str(otp)
        response = client.publish(
            PhoneNumber=phone_number,
            Message=msg,
            MessageStructure='string'
        )
    except KeyError:
        logger.debug("Error while sending the sms")
    else:
        logger.debug("Response: %s", json.dumps(response))        

def lambda_handler(event, context):
    logger.debug(json.dumps(event))
    method = event['httpMethod']
    object_key = event['pathParameters']['key']
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(u'smart-door-visitor')
    body = json.dumps({"status" : "true"})
    if method == "GET":
        obj = list(bucket.objects.filter(Prefix=object_key))
        img = ''
        if len(obj) > 0:
            obj = bucket.Object(key=object_key)     
            response = obj.get()
            img = response[u'Body'].read()
            img = [base64.b64encode(img)]
            logger.debug(str(img[0]))
            img = str(img[0]).replace("b'","")
            img = img.replace("'","")     
            logger.debug(img)
        body = json.dumps({"image" : img})  
        
    elif method == "POST":
        logger.debug(event['body'])
        details = json.loads(event['body'])
        name = details['name']
        phone = details['phone']
        table = get_table('virtual_door_visitors')
        owner_face_id = 'ef37eba3-9af6-49f6-929c-2fb25d25feea'
        if name and phone:
            face_id = create_index(object_key)
            item = {
                'face_id' : face_id,
                'full_name' : name,
                'phone_number' : phone,
                'photo' : [{
                    'objectKey': object_key, 
                    'bucket' : 'smart-door-visitor', 
                    'createdTimestamp' : str(time.ctime(time.time()))
                }]
            }
            try:
                table.put_item(Item = item)
                send_otp(face_id, phone)   
                copy_source = {
                    'Bucket': 'smart-door-visitor',
                    'Key': object_key
                }
                key = "known_faces/" + face_id + "/" + object_key
                s3.meta.client.copy(copy_source, 'smart-door-visitor', key)
            except ClientError as e:
                logger.debug("Error while updating owner record %s", e.response['Error']['Message'])
        else:
            copy_source = {
                    'Bucket': 'smart-door-visitor',
                    'Key': object_key
                }
            key = "unknown_faces/" + object_key
            s3.meta.client.copy(copy_source, 'smart-door-visitor', key)
        s3.Object('smart-door-visitor', object_key).delete()   
        try:
            # client = boto3.client('rekognition')
            # response = client.stop_stream_processor(
            #     Name='VirtualDoorSP'
            # )
            table.update_item(Key={'face_id': owner_face_id},
                UpdateExpression='SET is_occupied = :val1',
                ExpressionAttributeValues={
                    ':val1': 'false'
                }
            )
        except ClientError as e:
            logger.debug("Error while updating owner record %s", e.response['Error']['Message'])
        except Exception as e:
            logger.debug("Error while stopping stream %s" % str(e))     
        else:
            logger.debug("Owner made available")

    return {
        "statusCode": 200,
        "body": body,
        "headers":{ 'Access-Control-Allow-Origin' : '*', 'Access-Control-Allow-Headers' : 'Content-Type' }
    }
