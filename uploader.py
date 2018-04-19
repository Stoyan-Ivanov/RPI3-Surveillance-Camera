#!/usr/bin/env python3.4

# Developed by stoyan-ivanov
# Motion detect is kindly provided by Claude Pageau https://github.com/pageauc/pi-motion-lite


import dropbox
from dropbox.exceptions import ApiError, AuthError
import RPi.GPIO as GPIO
import time
import picamera.array
from fractions import Fraction
import datetime
import picamera
import sys, os
import smtplib

# Authorisation token
TOKEN = 'Your Token'

# Photo format (jpeg, jpg ..etc)
PHOTOFORMAT = 'jpeg'

# Motion Settings
threshold = 30     # How Much a pixel has to change
sensitivity = 300  # How Many pixels need to change for motion detection

# Camera Settings
testWidth = 640
testHeight = 480
nightShut = 5.5    # seconds Night shutter Exposure Time default = 5.5  Do not exceed 6 since camera may lock up
nightISO = 800
if nightShut > 6:
    nightShut = 5.9
SECONDS2MICRO = 1000000  # Constant for converting Shutter Speed in Seconds to Microseconds    
nightMaxShut = int(nightShut * SECONDS2MICRO)
nightMaxISO = int(nightISO)
nightSleepSec = 8   # Seconds of long exposure for camera to adjust to low light 


# Create a camera object and capture image using generated filename
def camCapture(filename):
    with picamera.PiCamera() as camera:
        camera.resolution = (testWidth, testHeight)

	overlayText = filename.strftime('%Y-%m-%d %H:%M:%S')
	filename = filename.strftime("%Y%m%d_%H%M%S")
        print("Photo: %s"%filename)

	camera.annotate_background = picamera.Color('black')
    	camera.annotate_text = overlayText
        time.sleep(2)
        camera.capture(filename + '.' + PHOTOFORMAT, format=PHOTOFORMAT)
        print("Photo captured and saved ...")
        return filename + '.' + PHOTOFORMAT


# Generate timestamp string generating name for photos
def generateTimestamp():
    tstring = datetime.datetime.now()
    print("Filename generated ...")
    return tstring


# Upload localfile to Dropbox
def uploadFile(localfile):

    # Check that access tocken added
    if (len(TOKEN) == 0):
        sys.exit("ERROR: Missing access token. "
                 "try re-generating an access token from the app console at dropbox.com.")

    # Create instance of a Dropbox class, which can make requests to API
    print("Creating a Dropbox object...")
    dbx = dropbox.Dropbox(TOKEN)

    # Check that the access token is valid
    try:
        dbx.users_get_current_account()
    except AuthError as err:
        sys.exit("ERROR: Invalid access token; try re-generating an "
                 "access token from the app console at dropbox.com.")

    # Specify upload path
    uploadPath = '/' + localfile

    # Read in file and upload
    with open(localfile, 'rb') as f:
        print("Uploading " + localfile + " to Dropbox as " + uploadPath + "...")

        try:
            dbx.files_upload(f.read(), uploadPath)
        except ApiError as err:
            # Check user has enough Dropbox space quota
            if (err.error.is_path() and
                    err.error.get_path().error.is_insufficient_space()):
                sys.exit("ERROR: Cannot upload; insufficient space.")
            elif err.user_message_text:
                print(err.user_message_text)
                sys.exit()
            else:
                print(err)
                sys.exit()


def sendEmail():

   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login("YOUR EMAIL ADDRESS", "YOUR PASSWORD")
 
   msg = "Warning! Motion has been detected!"
   server.sendmail("YOUR EMAIL ADDRESS", "THE EMAIL ADDRESS TO SEND TO", msg)
   server.quit()

# Delete file
def deleteLocal(file):
    os.system("rm " + file)
    print("File: " + file + " deleted ...")


def userMotionCode():
    print("Motion has been detected!")
    print("New photo will be captured ...")
    # Configure precapture light
    GPIO.output(26,GPIO.HIGH)
    
    # Generate name for file based on current time
    filename = generateTimestamp()

    # Capture photo
    photo = camCapture(filename)

    # Send warning email
    sendEmail()

    # Upload photo
    uploadFile(photo)

    # Delete local copy of the photo
    deleteLocal(photo)

    print("Uploaded!")
    GPIO.output(26,GPIO.LOW)

    return
            
def checkForMotion(data1, data2):
    # Find motion between two data streams based on sensitivity and threshold
    motionDetected = False
    pixColor = 1 # red=0 green=1 blue=2
    pixChanges = 0;
    for w in range(0, testWidth):
        for h in range(0, testHeight):
            # get the diff of the pixel. Conversion to int
            # is required to avoid unsigned short overflow.
            pixDiff = abs(int(data1[h][w][pixColor]) - int(data2[h][w][pixColor]))
            if  pixDiff > threshold:
                pixChanges += 1
            if pixChanges > sensitivity:
                break; # break inner loop
        if pixChanges > sensitivity:
            break; #break outer loop.
    if pixChanges > sensitivity:
        motionDetected = True
    return motionDetected 
    
         
def getStreamImage(daymode):
    # Capture an image stream to memory based on daymode
    isDay = daymode
    with picamera.PiCamera() as camera:
        time.sleep(.5)
        camera.resolution = (testWidth, testHeight)
        with picamera.array.PiRGBArray(camera) as stream:
            if isDay:
                camera.exposure_mode = 'auto'
                camera.awb_mode = 'auto' 
            else:
                # Take Low Light image            
                # Set a framerate of 1/6fps, then set shutter
                # speed to 6s and ISO to 800
                camera.framerate = Fraction(1, 6)
                camera.shutter_speed = nightMaxShut
                camera.exposure_mode = 'off'
                camera.iso = nightMaxISO
                # Give the camera a good long time to measure AWB
                # (you may wish to use fixed AWB instead)
                time.sleep( nightSleepSec )
            camera.capture(stream, format='rgb')
            return stream.array

def main():
    print("Surveillance has started!")
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(26,GPIO.OUT)

    dayTime = True
    stream1 = getStreamImage(dayTime)
    while True:
        stream2 = getStreamImage(dayTime)
        if checkForMotion(stream1, stream2):
            userMotionCode()
        stream1 = stream2        
    return
     
       
if __name__ == '__main__':
    try:
        main()
    finally:
        print("")
        print("+++++++++++++++++++")
        print("  Exiting Program")
        print("+++++++++++++++++++")
        print("")
               

