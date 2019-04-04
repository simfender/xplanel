#!/usr/bin/env python3

#      ELEGATO STREAM DECK - XPLANEL by Simfender
#
#	   Thanks to pyXPUDPServer and Python Stream Deck libraries

import json
import os
import asyncio
import socket
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
import pyxpudpserver as XPUDP

with open('config.json', 'r') as f:
    config = json.load(f)
	
drefcmds = config[config['MAIN']['SELECTED_AIRCRAFT']]['drefcmds']
imagesDir = config[config['MAIN']['SELECTED_AIRCRAFT']]['imgfolder']

keyNames = {}
keyStates = {}
keyStatesOld = {}
keyImagesOn = {}
keyImagesOff = {}

debug=True
	
XPUDP.pyXPUDPServer.initialiseUDP((config['MAIN']['SERVER_IP'],config['MAIN']['SERVER_PORT']), (config['MAIN']['XPLANE_IP'],config['MAIN']['XPLANE_PORT']), 'XPLANEL')
XPUDP.pyXPUDPServer.start()

# Generates a custom tile with run-time generated text and custom image via the
# PIL module.
def render_key_image(deck, icon_filename):
    # Create new key image of the correct dimensions, black background
    image = PILHelper.create_image(deck)
    draw = ImageDraw.Draw(image)

    # Add image overlay, rescaling the image asset if it is too large to fit
    # the requested dimensions via a high quality Lanczos scaling algorithm
    icon = Image.open(icon_filename).convert("RGBA")
    icon.thumbnail((image.width, image.height), Image.LANCZOS)
    image.paste(icon)

    return PILHelper.to_native_format(deck, image)


# Creates a new key image based on the key index, style and current key state
# and updates the image on the StreamDeck.
def update_key_image(deck, key, state, imageIn):

    # Generate the custom key with the requested image and label
    image = render_key_image(deck, imageIn)

    # Update requested key with the generated image
    deck.set_key_image(key, image)


# Prints key state change information, updates rhe key image and performs any
# associated actions when a key is pressed.
def key_change_callback(deck, key, state):

    try:    
        # Check if the key is changing to the pressed state
        if state:
	        # Print new key state
            keyStates[key]=not keyStates[key]
            if debug:
                print(keyNames[key]+"|{}|{}".format(key, keyStates[key]))
            # Update the key image based on the new key state
            #update_key_image(deck, key, state)				
            updateDeck()
			
            for x in drefcmds:
                if x['imgrefn']==keyNames[key]:
                    XPUDP.pyXPUDPServer.sendXPCmd(x['command'])
            # When an exit button is pressed, close the application
            if keyNames[key] == "exit":
                # Reset deck, clearing all button images
                deck.reset()
                # Close deck handle, terminating internal worker threads
                deck.close()
                innerCycle = False
    except KeyError:
        print ('NA')
		
def updateDeck():
    global keyStatesOld
    global keyImagesOn
    global streamdecks
    for index, deck in enumerate(streamdecks):
        if(keyStatesOld!=keyStates):	
            for key, status in keyStatesOld.items():
                 if(keyStates[key]!=keyStatesOld[key]):
                      if(keyStates[key]==True):
                          update_key_image(deck, key, False, keyImagesOn[key] )
                      else:
                          update_key_image(deck, key, False, keyImagesOff[key] )
                      keyStatesOld=keyStates.copy() 

					  
async def mainFunction():

    global streamdecks	
    streamdecks = DeviceManager().enumerate()

    global keyNames
    global keyStates
    global keyStatesOld 
    global keyImagesOn
    global keyImagesOff
    global innerCycle
    innerCycle = True

    if debug:
        print("Found {} Stream Deck(s).\n".format(len(streamdecks)))
	
    for index, deck in enumerate(streamdecks):
        deck.open()
        deck.reset()

        # Set initial screen brightness to 30%
        deck.set_brightness(100)
        buttonsImages = os.listdir(imagesDir);
        for i in range(len(buttonsImages)):
            splitFileName = buttonsImages[i].split(".")
            
            if splitFileName[2]=="off":
                update_key_image(deck, int(splitFileName[0]), False, imagesDir+buttonsImages[i] )
                keyNames[int(splitFileName[0])]=splitFileName[1]        
                keyStates[int(splitFileName[0])]=False	
                keyImagesOff[int(splitFileName[0])]=imagesDir+buttonsImages[i]		
            else:
                keyImagesOn[int(splitFileName[0])]=imagesDir+buttonsImages[i]			
		
        keyStatesOld=keyStates.copy()
        deck.set_key_callback(key_change_callback)

				 
def DecodePacket(data):
  retvalues = {}
  # Read the Header "RREFO".
  header=data[0:5]
  # We get 8 bytes for every dataref sent:
  #    An integer for idx and the float value. 
  values =data[5:]
  lenvalue = 8
  numvalues = int(len(values)/lenvalue)
  idx=0
  value=0
  for i in range(0,numvalues):
    singledata = data[(5+lenvalue*i):(5+lenvalue*(i+1))]
    (idx,value) = struct.unpack("<if", singledata)
    retvalues[idx] = (value, drefcmds[idx]['dataref'], drefcmds[idx]['command'] )
  return retvalues

async def subFunction():

  global keyStates
  global keyNames
  
  while True:
  
    time.sleep(0.1) 
    # Print Values:
    for x in drefcmds:
        val = XPUDP.pyXPUDPServer.getData(x['dataref'])
        if debug:		
            print(x['imgrefn'],val)
        if val > 0 :
            for button, name in keyNames.items():
                if name == x['imgrefn'] :
                    if debug:
                        print(name)
                    keyStates[button]=True
                    updateDeck()
        else:
            for button, name in keyNames.items():
                if name == x['imgrefn'] :
                    keyStates[button]=False
                    updateDeck()
        if debug:		
            print(x['dataref'],x['command'],x['imgrefn'])
            print(np.matrix(keyStates))

if __name__ == "__main__":
	
	# this is the event loop
    loop = asyncio.get_event_loop()
    # schedule both the coroutines to run on the event loop
    loop.run_until_complete(asyncio.gather(mainFunction(), subFunction()))
	
