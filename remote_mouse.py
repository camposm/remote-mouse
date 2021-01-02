#!/usr/bin/env python3

import os
import sys
import ssl
import socket
import struct
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpserver
import numpy as np
import pyautogui as pg
from enum import Enum

########################################################################################################################

config = {
    'mouse': {
        'beta_offset_deg':  0.0
    
    }
}

########################################################################################################################

# bit position in bitmask
class ButtonCodes(Enum):
    #
    MOUSE_LEFT      = 0
    MOUSE_RIGHT     = 1
    GP_BTN_0        = 2
    GP_BTN_1        = 3
    GP_BTN_2        = 4
    GP_BTN_3        = 5
    GP_BTN_4        = 6
    GP_BTN_5        = 7
    GP_BTN_6        = 8
    GP_BTN_7        = 9
    GP_BTN_8        = 10

class ButtonEventType(Enum):
    EVENT_DOWN      = 0
    EVENT_UP        = 1


class ActionProcessor:
    #
    def __init__ (self, config):
        #
        screen = pg.size()
        self.res_x = screen.width
        self.res_y = screen.height
        
        self.beta_offset = config['mouse']['beta_offset_deg']
        self.last_alpha = None

        self.x = self.res_x / 2
        self.y = self.res_y / 2
        
        self.button_states = {}
        self.button_down_callback = {}
        self.button_up_callback = {}
        
        self.register_callback(ButtonCodes.MOUSE_LEFT,  ButtonEventType.EVENT_DOWN, lambda: pg.mouseDown(button = 'left'))
        self.register_callback(ButtonCodes.MOUSE_LEFT,  ButtonEventType.EVENT_UP,   lambda: pg.mouseUp(button = 'left'))
        self.register_callback(ButtonCodes.MOUSE_RIGHT, ButtonEventType.EVENT_DOWN, lambda: pg.mouseDown(button = 'right'))
        self.register_callback(ButtonCodes.MOUSE_RIGHT, ButtonEventType.EVENT_UP,   lambda: pg.mouseUp(button = 'right'))

        pg.moveTo(self.res_x / 2, self.res_y / 2)
        
    def register_callback (self, button, event_type, function):
        #
        btn_mask = 1 << button.value
        
        if button not in self.button_states:
            self.button_states[btn_mask] = False
            
        if event_type == ButtonEventType.EVENT_DOWN:
            self.button_down_callback[btn_mask] = function
            return False
            
        elif event_type == ButtonEventType.EVENT_UP:
            self.button_up_callback[btn_mask] = function
            return False
            
        else:
            return True
    
    def update_orientation (self, alpha, beta):
        #
        self.y = int(self.res_y - (self.res_y * np.tan(np.deg2rad(beta - self.beta_offset))))
        
        if self.y < 0:
            self.y = 0
        if self.y > self.res_y:
            self.y = self.res_y
        
        if self.last_alpha is None:
            self.last_alpha = alpha
            return
            
        self.x -= int(2 * self.res_x * np.tan(np.deg2rad(alpha - self.last_alpha) / 2))
        self.last_alpha = alpha
        
        if self.x < 0:
            self.x = 0
        if self.x > self.res_x:
            self.x = self.res_x
        
        pg.moveTo(self.x, self.y)
                
    def update_user_input (self, button_map, v_scroll):
        #
        if abs(v_scroll) > 0.001:
            pg.scroll(v_scroll)

        for btn_mask in self.button_states:
            if button_map & btn_mask:
                self.button_states[btn_mask] = True
                if btn_mask in self.button_down_callback:
                    self.button_down_callback[btn_mask]()
            else:
                if self.button_states[btn_mask]:
                    self.button_states[btn_mask] = False
                    if btn_mask in self.button_up_callback:
                        self.button_up_callback[btn_mask]()
                        
    def handle_text_input (self, message):
        #
        if message == '\n':
            pg.press('enter')
        elif message == '\b':
            pg.press('backspace')
        else:
            pg.write(message)

class FileHandler(tornado.web.RequestHandler):
    #
    def get (self, fname):
        if fname == '':
            with open('index.html') as fin:
                self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.set_header("Content-Type", "text/html")
                self.write(fin.read())
        else:
            self.redirect('/')

class ControllerWebSocket(tornado.websocket.WebSocketHandler):
    #
    def initialize (self, action_processor):
        self.action_processor = action_processor
    
    def on_message(self, message):
        try:
            if len(message):
                hdr = bytes(struct.unpack('B', message[0:1]))
                if hdr == b'\xAA':
                    # orientation message
                    alpha, beta = struct.unpack('>ff', message[1:])
                    self.action_processor.update_orientation(alpha, beta)
                    
                elif hdr == b'\xBB':
                    # ui interaction message
                    button_map, v_scroll = struct.unpack('>If', message[1:])
                    self.action_processor.update_user_input(button_map, v_scroll)
            
        except Exception as e:
            print('error:', e)

class TextInputWebSocket(tornado.websocket.WebSocketHandler):
    #
    def initialize (self, action_processor):
        self.action_processor = action_processor
    
    def on_message(self, message):
        try:
            if len(message):
                self.action_processor.handle_text_input(message)
            
        except Exception as e:
            print('error:', e)

def main():
    #
    # remove delays in calls
    pg.PAUSE = 0
    # prevent pyautogui from blocking when mouse reaches a corner
    pg.FAILSAFE = 0
    
    AP = ActionProcessor(config)

    # demo
    for btn in ButtonCodes:
        if btn.value >= ButtonCodes.GP_BTN_0.value:
            AP.register_callback(
                btn, 
                ButtonEventType.EVENT_DOWN, 
                (lambda n: lambda: print("button {} down".format(n)))(btn.name)
            ) 
            AP.register_callback(
                btn, 
                ButtonEventType.EVENT_UP, 
                (lambda n: lambda: print("button {} up".format(n)))(btn.name)
            )
    
    app = tornado.web.Application(
        [
            (r"/ctrl", ControllerWebSocket, {'action_processor': AP}),
            (r"/text", TextInputWebSocket,  {'action_processor': AP}),
            (r"/(.*)", FileHandler),
        ], debug = False
    )
    
    if len(sys.argv) != 2:
        print("usage: {} port".format(sys.argv[0]))
        return
   
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(
        os.path.join(os.path.abspath("./keys"), "server.crt"),
        os.path.join(os.path.abspath("./keys"), "server.key")
    )
   
    server = tornado.httpserver.HTTPServer(app, ssl_options = ssl_ctx)
    server.listen(int(sys.argv[1]))
    tornado.ioloop.IOLoop.current().start()
    

if __name__ == "__main__":
    main()
