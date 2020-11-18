import json
import logging
import base64
import cv2
import boto3
import traceback
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

def generateOTP(): 
    digits = "0123456789"
    OTP = "" 
    for i in range(6) : 
        OTP += digits[math.floor(random.random() * 10)] 
    return OTP 

def extract_image(video_fragment):
    arn = video_fragment['StreamArn']
    num = video_fragment['FragmentNumber']
    client = boto3.client('kinesisvideo', region_name='us-east-1')
    response = client.get_data_endpoint(
        StreamARN=arn,
        APIName='GET_MEDIA_FOR_FRAGMENT_LIST',
    )
    client = boto3.client('kinesis-video-archived-media', endpoint_url=response['DataEndpoint'])
    response = client.get_media_for_fragment_list(
        StreamName='VirtualDoorStream',
        Fragments=[num]
    )
    chunk = response['Payload'].read()
    video_name = '/tmp/' + str(num) +'.webm'
    file_name = ''
    with open(video_name, 'wb+') as f:
        f.write(chunk)
        try:        
            cap = cv2.VideoCapture(video_name)
        except cv2.error as error:
            logger.debug('Error occured in cv2')
        except Exception as e:
            return ''
        ret, frame = cap.read()
        if ret:
            file_name = '/tmp/' + str(num) + '.jpg'
            cv2.imwrite(file_name, frame)
            cap.release()
    return file_name

def send_otp(face_id, phone_number, passcode_table):
    otp = generateOTP()
    exists = True
    while exists == True:
        response = passcode_table.query(
            KeyConditionExpression=Key('passcode').eq(otp)
        )
        if response['Items']:
            logger.debug("passcode found in the db")
            otp = generateOTP()
        else:
            exists = False
    passcode_table.put_item(Item = {'passcode' : otp, 'face_id' : face_id, 'passcode_time' : int(time.time() + 300)})        
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

def otp_exists(face_id, passcode_table):
    response = passcode_table.scan(
        FilterExpression=Attr('face_id').eq(face_id)
    )
    if response['Items']:
        return True
    else:
        return False
    
def process_matched_face(matched_faces, input_information):
    logger.debug("Total %s face matches found" % len(matched_faces))
    matched_face = matched_faces[0]
    table = get_table('virtual_door_visitors')
    face_id = matched_face["Face"]["FaceId"]
    try:
        response = table.query(
            KeyConditionExpression=Key('face_id').eq(face_id)
        )
        if not response['Items']:
           logger.debug("Face id not found in the db")
        else:
            passcode_table = get_table('virtual_door_passcodes')
            if not otp_exists(face_id, passcode_table):
                response = table.get_item(
                    Key={'face_id': face_id}
                )
                image_file = extract_image(input_information['KinesisVideo'])
                if not image_file:
                    logger.debug("No image file")
                    return
                client = boto3.client('s3')
                key = "known_faces/" + face_id + "/" + image_file.rsplit('/', 1)[-1]
                client.upload_file(image_file, 'smart-door-visitor', key)
                photo = {'objectKey': key, 'bucket' : 'smart-door-visitor', 'createdTimestamp' : str(time.ctime(time.time()))}
                table.update_item(
                    Key={'face_id': face_id},
                    UpdateExpression='SET photo = list_append(photo, :photo_obj)',
                    ExpressionAttributeValues={
                        ":photo_obj": [photo]
                    }
                )
                send_otp(face_id, response['Item']['phone_number'], passcode_table)
            else:
                logger.debug("OTP already sent for the face id %s" % face_id)
    except Exception as e:
        logger.error("Exception occured in process_matched_face(): %s" % str(e))
        track = traceback.format_exc()
        logger.error("Stacktrace %s" % track)
        

def process_unmatched_face(input_information):
    owner_face_id = 'ef37eba3-9af6-49f6-929c-2fb25d25feea'
    table = get_table('virtual_door_visitors')
    try:
        response = table.get_item(Key={'face_id': owner_face_id})
    except ClientError as e:
        logger.debug("Error while retrieving item from dynamodb %s", e.response['Error']['Message'])
    else:
        if response['Item']['is_occupied'] == 'false':
            image_file = extract_image(input_information['KinesisVideo'])
            if not image_file:
                logger.debug("No image file")
                return
            client = boto3.client('s3')
            key = image_file.rsplit('/', 1)[-1]
            client.upload_file(image_file, 'smart-door-visitor', key)
            url = "http://new-visitor.s3-website-us-east-1.amazonaws.com/?visitor=" + key
            sns = boto3.client('sns')
            msg = "You have a new visitor. Click on the link to perform your action. " + url
            # Publish a message to the specified SNS topic
            response = sns.publish(
                TopicArn='arn:aws:sns:us-east-1:642881259315:NewVisitor', 
                Subject='Hey, someone is at your door!',
                Message=msg,    
            )
            logger.debug("Sns response %s" % json.dumps(response))
            table.update_item(Key={'face_id': owner_face_id},
                UpdateExpression='SET is_occupied = :val1',
                ExpressionAttributeValues={
                    ':val1': 'true'
                }
            )

def lambda_handler(event, context):
    logger.debug("Events: %s" % json.dumps(event))
    processed_images = {}
    for record in event['Records']:
        logger.debug("Record: %s" % json.dumps(record))
        # Kinesis data is base64 encoded so decode here
        payload = base64.b64decode(record['kinesis']['data']).decode('utf-8')
        payload = json.loads(payload)
        logger.debug("Decoded payload: %s" % json.dumps(payload))
        try:
            if payload['FaceSearchResponse']:
                face_response = payload['FaceSearchResponse'][0]
                input_information = payload['InputInformation']
                matched_faces = face_response['MatchedFaces']
                if matched_faces:
                    logger.debug("Matches found")
                    process_matched_face(matched_faces, input_information)
                else:
                    logger.debug("No Matches found")
                    process_unmatched_face(input_information)
        except Exception as e:
            logger.debug("Exception occured %s" % str(e))
            track = traceback.format_exc()
            logger.debug("Stacktrace %s" % track)
        else:
            logger.debug("Successfully processed record sequence %s" % record['kinesis']['sequenceNumber'])
    logger.debug("Successfully processed %s records" % len(event['Records']))
    return {
        'statusCode': 200,
        'body': json.dumps('Success')
    }

