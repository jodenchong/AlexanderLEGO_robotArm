#!/usr/bin/env python3
#-- Python include
from enum import Enum, unique
import time
import threading
import json
import os
import sys
import logging
import random
from enum import Enum

#-- MQTT include
import paho.mqtt.client as mqtt

#-- EV3 include
from agt import AlexaGadget
from ev3dev2.led import Leds
from ev3dev2.sound import Sound
from ev3dev2.motor import MediumMotor, MoveTank, OUTPUT_B, OUTPUT_C
from ev3dev.auto import *

# Set the logging level to INFO to see messages from AlexaGadget
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(message)s')
logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
logger = logging.getLogger(__name__)

#------------------------------------------ Read init File ----------------------------------
with open('init.txt', 'r', encoding="utf-8") as initFile:
    eve3Init = json.load(initFile)
    initFile.close()
    print(eve3Init.get('name','name not fround'))

#------------------------------------------ Variable Init ----------------------------------
homing_task = 0
publishTitle = "in/motor/"  +  eve3Init["name"]
subscribeTitle = "out/motor/" +  eve3Init["name"]

mtrdir      = 0
mtrspeeddt  = 0
mtrdelayF   = 0
mtrdelay    = 0
motorTask_step    = 0
motorTask_temp    = "0"
version     = "V7"

#------------------------------------------ Hardware init ----------------------------------
leds = Leds()
sound = Sound()
if eve3Init["name"] != "RA":
    M1 = MediumMotor('outA')   #largeMotor max RPM is 175
    M2 = MediumMotor('outB')
    M3 = MediumMotor('outC')
    M4 = MediumMotor('outD')
else:
    M1 = MediumMotor('outA')
    M2 = MediumMotor('outB')
    M3 = MediumMotor('outC')

motorList = ['off','off','off','off']
if M1.connected:
    print('M1 is connected')
    motorList[0] = 'on'
    M1.stop()
else: 
    print('M1 is not connected')
if M2.connected:
    print('M2 is connected')
    motorList[1] = 'on'
    M2.stop()
else: 
    print('M2 is not connected')
if M3.connected:
    print('M3 is connected')
    motorList[2] = 'on'
    M3.stop()
else: 
    print('M3 is not connected')
if M4.connected:
    print('M4 is connected')
    motorList[3] = 'on'
    M4.stop()
else: 
    print('M4 is not connected')

class MindstormsGadget(AlexaGadget):
    """
    A Mindstorms gadget that performs movement based on voice commands.
    """

    def __init__(self):
        """
        Performs Alexa Gadget initialization routines and ev3dev resource allocation.
        """
        super().__init__()

    def on_connected(self, device_addr):
        """
        Gadget connected to the paired Echo device.
        :param device_addr: the address of the device we connected to
        """
        leds.set_color(leds.LEFT, leds.GREEN)
        leds.set_color(leds.RIGHT, leds.GREEN)
        logger.info("{} connected to Echo device".format(self.friendly_name))

    def on_disconnected(self, device_addr):
        """
        Gadget disconnected from the paired Echo device.
        :param device_addr: the address of the device we disconnected from
        """
        leds.all_off()
        logger.info("{} disconnected from Echo device".format(self.friendly_name))

    def on_custom_mindstorms_gadget_control(self, directive):
        global motorTask_temp
        global motorTask_step
        """
        Handles the Custom.Mindstorms.Gadget control directive.
        :param directive: the custom directive with the matching namespace and name
        """
        try:
            payload = json.loads(directive.payload.decode("utf-8"))
            print("Control payload: {}".format(payload), file=sys.stderr)
            control_type = payload["type"]

            if control_type == "number":
                print("number",payload["number"])
                motorTask_temp = str(payload["number"])
                print(motorTask_temp)
                motorTask_step = 1

            if control_type == "command":
                print("command",payload["command"])

        except KeyError:
            print("Missing expected parameters: {}".format(directive), file=sys.stderr)


#------------------------------------------ MQTT ----------------------------------
def on_connect(client, userdata, flags, rc):
    global publishTitle
    global subscribeTitle
    global eve3Init
    # update motor status through MQTT
    print('MQTT Conneted')
    stringtemp2 = eve3Init["name"] +" "+ version + " online A:" + motorList[0] + " B:" + motorList[1] + " C:" + motorList[2] + " D:" + motorList[3]
    client.subscribe(subscribeTitle)
    client.publish (publishTitle, stringtemp2)


def on_message(client, userdata, msg):
    m_decode=str(msg.payload.decode("utf-8","ignore"))
    m_in=json.loads(m_decode) #decode json data

    global eve3Init
    global mtrdir
    global mtrspeeddt
    global mtrdelayF
    global mtrdelay
    global motorTask_step
    global motorTask_temp
    global homing_task

    # Stop all tasks and motors
    if m_in.get('stop') != None:
        M1.stop()
        M2.stop()
        M3.stop()
        M4.stop()
        homing_task = 5 # stop homing sequence
        print("Stop all motor")

    # All motor homing sequence
    elif m_in.get('home') != None and eve3Init["name"] != "RA":
        mtrdir = m_in["dir"]            # Motor moveing direction
        mtrspeeddt = m_in["speeddt"]    # Motor Speed
        mtrdelayF = m_in["delayf"]      # Start sequence delay
        mtrdelay = m_in["delay"]        # Sequence end delay
        homing_task = 1

    # Single motor homing sequence
    # Exp: {"motor":1,"dir":200,"speeddt":190,"delayf":1.5,"delay":0.08}
    elif m_in.get('motorH') != None:
        if m_in['motorH'] == 1:
            motorHome2(M1,m_in["dir"],m_in["speeddt"],m_in["delayf"],m_in["delay"])
        if m_in['motorH'] == 2:
            motorHome2(M2,m_in["dir"],m_in["speeddt"],m_in["delayf"],m_in["delay"])
        if m_in['motorH'] == 3:
            motorHome2(M3,m_in["dir"],m_in["speeddt"],m_in["delayf"],m_in["delay"])
        if m_in['motorH'] == 4 and eve3Init["name"] != "RA":
            motorHome2(M4,m_in["dir"],m_in["speeddt"],m_in["delayf"],m_in["delay"])

    # Execute sign language sequence
    elif m_in.get('alphabet') != None:
        motorTask_temp = m_in["alphabet"]
        print(motorTask_temp)
        motorTask_step = 1

    # Execute multiple absolute position movements
    # Exp: {"motorCmd":1,"1":{"pos":-2000,"speed":200,"delay":5},"2":{"pos":10,"speed":200,"delay":5},"3":{"pos":-2000,"speed":200,"delay":5},"4":{"pos":-1000,"speed":200,"delay":5}}
    elif m_in.get('motorCmd') != None: # change this 
        for key in range(len(m_in)):
            value = str(key)
            if m_in.get(value) != None:
                value2 = m_in[value]
                print("%d = pos:%d, speed:%d, delay:%d" % (key, value2["pos"], value2["speed"],value2["delay"])) 
                if value == "1":
                    M1.run_to_abs_pos(position_sp =value2["pos"],speed_sp=value2["speed"])
                    time.sleep(value2["delay"])
                if value == "2":
                    M2.run_to_abs_pos(position_sp =value2["pos"],speed_sp=value2["speed"])
                    time.sleep(value2["delay"])
                if value == "3":
                    M3.run_to_abs_pos(position_sp =value2["pos"],speed_sp=value2["speed"])
                    time.sleep(value2["delay"])
                if value == "4":
                    M4.run_to_abs_pos(position_sp =value2["pos"],speed_sp=value2["speed"])
                    time.sleep(value2["delay"])

    # Execute single absolute position movements
    # Exp: {"motorAbs":1,"pos":-500,"speed":200} 
    elif m_in.get('motorAbs') != None:
        tempVl1 = m_in["pos"]
        # print("abs pos start %d" % tempVl1)
        tempVl2 = m_in["speed"]
        if m_in['motor'] == 1:
            M1.run_to_abs_pos(position_sp =tempVl1,speed_sp=tempVl2)
            print("M1  run to abs pos %d" % tempVl1)
        elif m_in['motor'] == 2:
            M2.run_to_abs_pos(position_sp =tempVl1,speed_sp=tempVl2)
            print("M2  run to abs pos %d" % tempVl1)
        elif m_in['motor'] == 3:
            M3.run_to_abs_pos(position_sp =tempVl1,speed_sp=tempVl2)
            print("M3  run to abs pos %d" % tempVl1)
        elif m_in['motor'] == 4:
            M4.run_to_abs_pos(position_sp =tempVl1,speed_sp=tempVl2)
            print("M4  run to abs pos %d" % tempVl1)

    else:
        print("Command not found")


#========================================= Motor Function =========================================
def abs_pos(motor,pos,speedFc,delayFc):
    """
    Execute absolute position movements
    :param motor: number 1 represent motor "outA", 2 = "outB", 3 = "outC", 4 = "outD"
    :param pos: position set point
    :param speedFc: The speed percentage as an integer
    :param delayFc: Sequence delay
    """
    if motor == 1:
        M1.run_to_abs_pos(position_sp =pos,speed_sp=speedFc)
    elif motor == 2:
        M2.run_to_abs_pos(position_sp =pos,speed_sp=speedFc)
    elif motor == 3 and eve3Init["name"] != "RA":
        M3.run_to_abs_pos(position_sp =pos,speed_sp=speedFc)
    elif motor == 4 and eve3Init["name"] != "RA":
        M4.run_to_abs_pos(position_sp =pos,speed_sp=speedFc)
    time.sleep(delayFc)


#========================================= Motor =========================================
def motorHome2(motor,speedSp,speeddt,delayf,delay):
    motor.run_forever(speed_sp=speedSp)
    time.sleep(delayf)
    if speedSp > 0:
        while True:
            if motor.speed < speeddt:
                print(motor.speed)
                motor.stop()
                break
            time.sleep(delay)
    else:
        while True:
            if motor.speed > speeddt:
                print(motor.speed)
                motor.stop()
                break
            time.sleep(delay)
    motor.position = 0


def motorHome(motor,speedSp):
    task  = 1
    delay = 2
    while task:       
        if task == 1:
            # print("p1")
            motor.run_forever(speed_sp=speedSp)
            delay = 0.06
            task += 1
        elif task == 2:
            # print("p2")
            positionA = motor.position
            delay = 0.015
            task += 1
        elif task == 3:
            # print("p3")
            positionB = motor.position
            if positionA - positionB == 0:
                print("p4 end")
                delay = 0.5
                motor.stop()
                task = 0
            else:
                task = 2
                delay = 0.015
        time.sleep(delay)  
    # return True


def motor_Task():
    global eve3Init
    global motorTask_step
    global motorTask_temp
    global client
    with open('actionTasks.json', 'r', encoding="utf-8") as actionTaskFile:
        actionTask = json.load(actionTaskFile)
        actionTaskFile.close()
    actionTaskTemp = actionTask["tasks"]
    if actionTaskTemp.get(motorTask_temp) != None:
        print("Starting",motorTask_temp ,"task")
        for key in range(len(actionTaskTemp[motorTask_temp]['machine'])):
            value = int(key)
            machineName = actionTaskTemp[motorTask_temp]['machine'][value]['name']
            print(machineName)
            if machineName == eve3Init["name"]:
                action1 = actionTaskTemp[motorTask_temp]['machine'][value]['action']
                for key2 in range(len(action1)):
                    value2 = int(key2)
                    print("Motor:%d func:%s sp:%d pos:%d dy:%d" % \
                            (action1[value2]['motor'],  \
                            action1[value2]['function'], \
                            action1[value2]['speed'],   \
                            action1[value2]['pos'],     \
                            action1[value2]['delay']))
                    if action1[value2]['function'] == "abs":
                        abs_pos(action1[value2]['motor'],action1[value2]['pos'],action1[value2]['speed'],action1[value2]['delay'])
            else:
                sendToSlaveTitle = "out/motor/" +  machineName
                print("send to",sendToSlaveTitle)
                action1 = actionTaskTemp[motorTask_temp]['machine'][value]['action']
                for key2 in range(len(action1)):
                    value2 = int(key2)
                    print("Motor:%d func:%s sp:%d pos:%d dy:%d" % \
                            (action1[value2]['motor'],  \
                            action1[value2]['function'], \
                            action1[value2]['speed'],   \
                            action1[value2]['pos'],     \
                            action1[value2]['delay']))
                    delay1 = action1[value2]['delay']
                    string1 = action1[value2]
                    string1["delay"] = 0
                    string1["motorAbs"] = 1
                    print("string1 =",string1)
                    string2 = json.dumps(string1)
                    print("string1 JSON=",string2)
                    client.publish(sendToSlaveTitle,string2)
                    time.sleep(delay1)
    else:
        print("Not alphabet %s task" % motorTask_temp)


#========================================= Main =========================================
def main():
    global mainLoop 
    mainLoop = True
    delay = 1
    global homing_task
    global mtrdir
    global mtrspeeddt
    global mtrdelayF
    global mtrdelay
    global motorTask_step
    while mainLoop:
        if homing_task == 1:
            print("M1 homing") 
            motorHome2(M1,mtrdir,mtrspeeddt,mtrdelayF,mtrdelay) 
            print("M1 at position %d" % M1.position) 
            homing_task += 1
        elif homing_task == 2:
            print("M2 homing")
            motorHome2(M2,mtrdir,mtrspeeddt,mtrdelayF,mtrdelay) 
            print("M2 at position %d" % M2.position) 
            homing_task += 1
        elif homing_task == 3:
            print("M3 homing")
            motorHome2(M3,mtrdir,mtrspeeddt,mtrdelayF,mtrdelay) 
            print("M3 at position %d" % M3.position) 
            homing_task += 1
        elif homing_task == 4:
            print("M4 homing")
            motorHome2(M4,mtrdir,mtrspeeddt,mtrdelayF,mtrdelay) 
            print("M4 at position %d" % M4.position) 
            homing_task = 0
        elif homing_task == 5:
            homing_task = 0
            M1.stop()
            M2.stop()
            M3.stop()
            M4.stop()

        if motorTask_step:
            motorTask_step = 0
            motor_Task()

        time.sleep(1)

    M1.stop()
    M2.stop()
    M3.stop()
    M4.stop()


if __name__ == '__main__':
    # ------------- MQTT -------------- #
    client = mqtt.Client()
    client.connect("192.168.0.103",1883,60)

    client.on_connect = on_connect
    client.on_message = on_message
    client.username_pw_set("admin", "1234")

    # ------------- main program threading -------------- #
    threading.Thread(target=main, daemon=True).start()

    sound.play_song((('C4', 'e'), ('D4', 'e'), ('E5', 'q')))
    leds.set_color(leds.LEFT, leds.GREEN)
    leds.set_color(leds.RIGHT, leds.GREEN)
    
    if eve3Init["name"] != "RH":
        print("Start MQTT client Loop")
        client.loop_forever()
    else:
        threading.Thread(target=client.loop_forever, daemon=True).start()
        print("Start Gadget main")
        gadget = MindstormsGadget()
        gadget.main()

    # ------------- Shutdown sequence -------------- #
    mainLoop = False
    client.loop_stop()

    sound.play_song((('E5', 'e'), ('C4', 'e')))
    leds.all_off()

    print("Shutdown")

