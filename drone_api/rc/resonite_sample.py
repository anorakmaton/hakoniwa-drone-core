#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import libs.hakosim as hakosim
import time
import math
import numpy
import pprint

def transport(client, baggage_pos, transfer_pos):
    client.moveToPosition(baggage_pos['x'], baggage_pos['y'], 3, 0, -90)
    client.moveToPosition(baggage_pos['x'], baggage_pos['y'], 3, 5)
    client.moveToPosition(baggage_pos['x'], baggage_pos['y'], 3, 5, 0)
    client.moveToPosition(baggage_pos['x'], baggage_pos['y'], 0.7, 0.01, 0)

    client.moveToPosition(baggage_pos['x'], baggage_pos['y'], 3, 0.01)
    client.moveToPosition(transfer_pos['x'], transfer_pos['y'], 3, 0.1)
    client.moveToPosition(transfer_pos['x'], transfer_pos['y'], transfer_pos['z'], 0.01)

    client.moveToPosition(transfer_pos['x'], transfer_pos['y'], 3, 0.01)

def debug_pos(client):
    pose = client.simGetVehiclePose()
    print(f"POS  : {pose.position.x_val} {pose.position.y_val} {pose.position.z_val}")
    roll, pitch, yaw = hakosim.hakosim_types.Quaternionr.quaternion_to_euler(pose.orientation)
    print(f"ANGLE: {math.degrees(roll)} {math.degrees(pitch)} {math.degrees(yaw)}")



def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <config_path>")
        return 1

    # connect to the HakoSim simulator
    client = hakosim.MultirotorClient(sys.argv[1])
    client.confirmConnection()
    client.enableApiControl(True)
    client.armDisarm(True)


    client.takeoff(3)
    baggage_pos = { "x": 0, "y": 3 }
    transfer_pos = { "x": 0, "y": -1, "z": 0.7 }
    transport(client, baggage_pos, transfer_pos)
    debug_pos(client)

    baggage_pos = { "x": 0, "y": 4 }
    transfer_pos = { "x": 0, "y": -1, "z": 1.2 }
    transport(client, baggage_pos, transfer_pos)
    debug_pos(client)

    client.moveToPosition(-2, -1, 3, 5)
    debug_pos(client)
    time.sleep(3)
    client.moveToPosition(-2, -1, 0.3, 5)
    debug_pos(client)
    time.sleep(3)

    client.land()
    debug_pos(client)

    print('DONE')

    return 0

if __name__ == "__main__":
    sys.exit(main())
