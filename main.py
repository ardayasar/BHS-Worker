import datetime
from networkJobs import networkJobs
from fileJobs import fileJobs
# import RPi.GPIO as GPIO
# import keyboard
from pynput.keyboard import Listener
from threading import Thread
import time
import os
import dotenv
import subprocess
import random
from anydesk import anydesk
from printerDrivers import printerDriver

adk = anydesk()

dotenv.load_dotenv(dotenv_path='home/pi/Desktop/BHS-Upgrader/.env')

keyboard_pins = ["1", "2", "3", "4", "5", "6"]

config = {
    'deviceID': os.getenv("DEVICEID"),
    'authKey': os.getenv("AUTHKEY"),
    'isRegistered': False,
    'fileLocation': os.getcwd() + "/versions/" + str(os.getenv('VERSION')) + "/pdf/",
    'isActive': False,
    'buttonCount': 0,
    'isBetweenTime': False,
    'deviceStartTime': datetime.time(9, 0),
    'deviceEndTime': datetime.time(17, 0),
    'device_second_StartTime': datetime.time(1, 0),
    'device_second_EndTime': datetime.time(8, 0),
    'isDelayAvailable': False,
    'printer_information': ""
}


def asyncDevice():
    while True:
        try:
            NJ = networkJobs(config['deviceID'], config['authKey'])
            config['isRegistered'] = NJ.isRegistered()
            config['isActive'] = NJ.isActive()
            bc = NJ.getButtonCount()
            if bc > 0:
                config['buttonCount'] = bc
            else:
                quit("Button count problem")

            FJ = fileJobs(config['buttonCount'], config['fileLocation'])
            FJ.generateFolders()

            fileList = []

            for folder in range(config['buttonCount']):
                folder += 1
                result = FJ.getFiles(folder)
                fileList.append(result)

            jobList = NJ.asyncFiles(fileList)
            print(jobList)
            for folder in range(len(jobList)):
                FJ.deleteFiles(folder+1, jobList[folder][0])
                for file in jobList[folder][1]:
                    content = NJ.downloadFile(file)
                    if not content:
                        continue
                    FJ.saveFile(folder+1, file, content)

            for folder in range(config['buttonCount']):
                path = config['fileLocation'] + str(folder+1)
                files = os.listdir(path)
                for file in files:
                    lpath = config['fileLocation'] + str(folder + 1)
                    lpath += "/" + file
                    if os.path.getsize(lpath) < 10:
                        os.remove(lpath)

            # print(jobList)
            working_times = NJ.getWorkingTimes()
            config['deviceStartTime'] = working_times[0][0]
            config['deviceEndTime'] = working_times[0][1]
            config['device_second_StartTime'] = working_times[1][0]
            config['device_second_EndTime'] = working_times[1][1]

            time.sleep(300)
        except Exception as e:
            print(e)
            time.sleep(10)


def checkPrinter():
    try:
        NJ = networkJobs(config['deviceID'], config['authKey'])
        printer_information = NJ.getPrinterInformation()
        printer_driver = printerDriver(printer_information['printerName'], printer_information['printerManufacturer'], printer_information['printerID'])
        last_call = ""
        while True:
            try:
                printer_status, level_code = printer_driver.getStatus()
                if printer_status != last_call:
                    last_call = printer_status
                    NJ.updatePrinterStatus(printer_status, level_code)
                time.sleep(360)
            except Exception as e:
                print(e)
                time.sleep(360)
    except Exception as e:
        while True:
            print("Printer is offline. To reactivate, please connect to wifi and restart device")
            time.sleep(360)


NJ = networkJobs(config['deviceID'], config['authKey'])

if not NJ.isRegistered():
    if NJ.setup():
        print("Setup request has been sent to server!")
    else:
        quit("There was a problem while setting up the device!")
else:
    config['isRegistered'] = True

if os.getenv("ANYDESK") == "0":
    try:
        if adk.generateId():
            time.sleep(10)
            if adk.setPassword("fattoli3417"):
                time.sleep(4)
                anyID = adk.getId()
                if NJ.updateAnyDeskInfo(anyID, os.getenv("PASSWORD")):
                    # dotenv.set_key("../../.env", "ANYDESK", anyID)
                    print("Setup completed")
    except Exception as e:
        print(e, 'anydesk')

while not config["isRegistered"]:
    if NJ.isRegistered():
        print("Verified")
        config['isRegistered'] = True
        bc = NJ.getButtonCount()
        if bc > 0:
            config['buttonCount'] = bc
        else:
            quit("Button count problem")
    else:
        time.sleep(10)


deviceAsync = Thread(target=asyncDevice)
deviceAsync.start()

printerStatus = Thread(target=checkPrinter)
printerStatus.start()

FJ = fileJobs(config['buttonCount'], config['fileLocation'])


def controlKey(input_key):
    try:
        input_key = int(str(input_key).replace("'", ''))
    except Exception as e:
        lsp = []
        for i in range(config['buttonCount']):
            lsp.append(False)
        # print(e)
        return lsp

    lsl = []
    for i in range(config['buttonCount']):
        apData = False
        if i+1 == input_key:
            apData = True

        lsl.append(apData)

    return lsl


def onButtonPress(key):
    # print(key)
    if str(key).replace("'", '') == 'q':
        quit()


def onButtonRelease(pushedButton, listener):
    try:

        if config['isDelayAvailable'] == True:
            return

        if config['isActive'] and config['isRegistered']:
            pinStatus = controlKey(pushedButton)

            if True in pinStatus:
                config['isDelayAvailable'] = True
                for pin_slot in range(len(pinStatus)):
                    if pinStatus[pin_slot]:
                        filePath = config['fileLocation'] + str(pin_slot+1) + "/"
                        pathFiles = FJ.getFiles(pin_slot+1)
                        pathLen = len(pathFiles)
                        if pathLen > 0:
                            selectedFile = random.randint(1, pathLen)
                            selectedFile_name = pathFiles[selectedFile-1]
                            selectedFile_path = filePath + selectedFile_name
                            subprocess.run(['cancel', '-a'])
                            subprocess.run(["lp", "-o fit-to-page", selectedFile_path + '.pdf'], capture_output=True)
                            print('Printing -> ' + selectedFile_path)
                            os.environ['printCount'] = str(int(os.getenv('printCount')) + 1)
                            # dotenv.set_key('home/pi/Desktop/BHS-Upgrader/.env', "printCount", os.environ["printCount"])
                            listener.stop()
                            # listener.join()
                            time.sleep(5)
                            config['isDelayAvailable'] = False
                            run_listener()
                            continue
                        else:
                            print("Selected buttons file is empty. Please assign a category or add story to category")
                            time.sleep(3)
                            config['isDelayAvailable'] = False

            # print(pinStatus)
            time.sleep(0.4)
    except Exception as e:
        print(e)
        print("Error")

def is_time_in_range(start, end):
    current_time = datetime.datetime.now().time()
    if start <= end:
        return start <= current_time <= end
    else:
        return start <= current_time or current_time <= end


def run_listener():
    listener = Listener(on_press=None, on_release=lambda key: onButtonRelease(key, listener))
    listener.start()
    return listener


listener = run_listener()

while True:
    if is_time_in_range(config['deviceStartTime'], config['deviceEndTime']) or is_time_in_range(config['device_second_StartTime'], config['device_second_EndTime']):
        if listener is None or not listener.is_alive():
            listener = run_listener()
    else:
        try:
            listener.stop()
            # listener.join()
            listener = None
        except Exception as e:
            print(e)
    time.sleep(30)
