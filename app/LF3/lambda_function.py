import json
import logging
import boto3
from boto3.dynamodb.conditions import Key, Attr


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def get_table(table_name):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    return table

def startStream():
    try:
        client = boto3.client('rekognition')
        response = client.start_stream_processor(
            Name='VirtualDoorSP'
        )
        logger.debug(json.dumps(response))
    except Exception as e:
        logger.debug("Error while starting stream")
    
def stopStream(otp):
    try:
        client = boto3.client('rekognition')
        # response = client.stop_stream_processor(
        #     Name='VirtualDoorSP'
        # )
    except Exception as e:
        logger.debug("Error while stopping stream")    
    if otp:
        table = get_table('virtual_door_passcodes')
        response = table.query(
                KeyConditionExpression=Key('passcode').eq(otp)
        )
        # if response['Items']:
        #     try:
        #         res = table.delete_item(Key={'passcode': otp})
        #     except Exception as e:
        #         logger.error('Error while deleting otp  %s' % otp)
        #         logger.error('Error:  %s' % str(e))
    

def get_name(face_id):
    table = get_table("virtual_door_visitors")
    try:
        response = table.get_item(Key={'face_id': face_id})
    except boto.dynamodb.exceptions.DynamoDBKeyNotFoundError:
        logger.error('Record with face_id %s not found' % face_id)
    else:    
        return response['Item']['full_name']

def validate_otp(otp):
    status, name = False, ''
    table = get_table('virtual_door_passcodes')
    response = table.query(
            KeyConditionExpression=Key('passcode').eq(otp)
    )
    if response['Items']:
        status = True
        logger.debug("passcode found in the db")
        name = get_name(response['Items'][0]['face_id'])
    return status, name
    
def lambda_handler(event, context):
    logger.debug(json.dumps(event))
    resource = event['resource']
    method  = event['httpMethod']
    body =  json.dumps({
        "status": "true"
    })
    if resource == '/stream' and method == 'POST':
        details = json.loads(event['body'])
        action = details['action']
        otp = details['otp']
        if action == "start":
            startStream()
        elif action == "stop":
            stopStream('')
        elif action == "stop_and_expire":
            stopStream(otp)
        body =  json.dumps({
            "status": "true"
        })   
    if resource == '/passcode' and method == 'POST':
        details = json.loads(event['body'])
        otp = details['otp']
        status, name = validate_otp(otp)
        body =  json.dumps({
            "status":status,
            "name":name
        }) 
            
    return {
        "statusCode": 200,
        "body": body,
        "headers":{ 'Access-Control-Allow-Origin' : '*', 'Access-Control-Allow-Headers' : 'Content-Type' }
    }
